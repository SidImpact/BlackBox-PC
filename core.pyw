import time
import os
import pyautogui
import threading
import sqlite3
import ctypes  
import subprocess  # NEW: Used to open the viewer window independently
from datetime import datetime, timedelta  
from pynput import mouse, keyboard
from PIL import Image, ImageDraw, ImageGrab  # UPGRADED: Added ImageGrab for multi-monitor capture
import pystray  # NEW: Handles the Windows System Tray interface
import asyncio  # NEW: Handles asynchronous OCR operations
import sys  # NEW: Handles encoding protection

def safe_print(msg):
    try:
        enc = sys.stdout.encoding or 'utf-8'
        print(msg.encode(enc, errors='replace').decode(enc))
    except:
        try:
            print(msg.encode('ascii', errors='replace').decode('ascii'))
        except:
            pass

# CONFIGURATION
log_folder = "BlackBox_Logs"
CURSOR_SCALE = 2 
DB_NAME = "blackbox_v5.db"  

# GLOBAL CONTROLS
is_paused = False
icon_instance = None
mouse_listener = None
keyboard_listener = None

# Throttling configuration
last_capture_time = 0
last_captured_app = ""
MIN_CAPTURE_INTERVAL = 2.0  # seconds cooldown

if not os.path.exists(log_folder):
    os.makedirs(log_folder)

def setup_database():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ActionLogs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            trigger_reason TEXT,
            file_path TEXT,
            app_name TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    cursor.execute("INSERT OR IGNORE INTO Settings (key, value) VALUES ('retention', 'Never')")
    cursor.execute("INSERT OR IGNORE INTO Settings (key, value) VALUES ('blacklist', '1Password, Bitwarden, Incognito, Online Banking')")
    
    # Dynamically check if ocr_text column exists
    cursor.execute("PRAGMA table_info(ActionLogs)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'ocr_text' not in columns:
        cursor.execute("ALTER TABLE ActionLogs ADD COLUMN ocr_text TEXT")
        
    conn.commit()
    conn.close()

def run_storage_cleanup():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM Settings WHERE key = 'retention'")
    result = cursor.fetchone()
    retention = result[0] if result else "Never"
    
    if retention == "Never":
        safe_print("🧹 Storage Manager: Retention set to 'Never'. History preserved.")
        conn.close()
        return

    days = int(retention.split()[0])
    cutoff_date = datetime.now() - timedelta(days=days)
    cutoff_str = cutoff_date.strftime("%Y%m%d_%H%M%S")
    
    cursor.execute("SELECT file_path FROM ActionLogs WHERE timestamp < ?", (cutoff_str,))
    expired_logs = cursor.fetchall()
    
    if expired_logs:
        deleted_count = 0
        for (file_path,) in expired_logs:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    deleted_count += 1
                except:
                    pass
        cursor.execute("DELETE FROM ActionLogs WHERE timestamp < ?", (cutoff_str,))
        conn.commit()
        safe_print(f"🧹 Storage Manager: Cleaned {deleted_count} old frames.")
    conn.close()

# Initialize DB and clean storage
setup_database()
run_storage_cleanup()

capture_lock = threading.Lock()

def get_active_window_title():
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value if buf.value else "Desktop / Unknown"
    except:
        return "Unknown Application"

def get_blacklist():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM Settings WHERE key = 'blacklist'")
        res = cursor.fetchone()
        conn.close()
        if res:
            return [word.strip().lower() for word in res[0].split(",") if word.strip()]
    except:
        pass
    return ["1password", "bitwarden", "incognito", "online banking"]

def run_ocr_in_background(filepath, log_id):
    async def process():
        try:
            import winrt.windows.storage as wstorage
            import winrt.windows.media.ocr as wocr
            import winrt.windows.graphics.imaging as wimaging
            
            abs_path = os.path.abspath(filepath)
            if not os.path.exists(abs_path):
                return
                
            file = await wstorage.StorageFile.get_file_from_path_async(abs_path)
            stream = await file.open_async(wstorage.FileAccessMode.READ)
            decoder = await wimaging.BitmapDecoder.create_async(stream)
            bitmap = await decoder.get_software_bitmap_async()
            
            engine = wocr.OcrEngine.try_create_from_user_profile_languages()
            if not engine:
                available = wocr.OcrEngine.get_available_recognizer_languages()
                if available:
                    engine = wocr.OcrEngine.try_create_from_language(available[0])
            
            if engine:
                result = await engine.recognize_async(bitmap)
                ocr_text = result.text
                
                # Save back to SQLite
                conn = sqlite3.connect(DB_NAME)
                cursor = conn.cursor()
                cursor.execute("UPDATE ActionLogs SET ocr_text = ? WHERE id = ?", (ocr_text, log_id))
                conn.commit()
                conn.close()
        except Exception as e:
            safe_print(f"Background OCR Error: {e}")
            
    asyncio.run(process())

def capture_screen_in_background(trigger_reason, mouse_pos, app_name):
    global last_capture_time, last_captured_app
    
    if is_paused:  # NEW: Drop frames immediately if user has paused recording
        return
        
    # 1. Privacy Blacklist Filter
    blacklist = get_blacklist()
    app_lower = app_name.lower()
    for keyword in blacklist:
        if keyword in app_lower:
            safe_print(f"Auto-paused logging: '{app_name}' matches blacklist keyword '{keyword}'")
            return
            
    # 2. Intelligent Throttling
    current_time = time.time()
    if app_name == last_captured_app and (current_time - last_capture_time < MIN_CAPTURE_INTERVAL):
        return
        
    if not capture_lock.acquire(blocking=False):
        return 
        
    try:
        last_capture_time = current_time
        last_captured_app = app_name
        
        timestamp = time.strftime("%Y%m%d_%H%M%S") + f"_{int(time.time() * 1000) % 1000:03d}"
        filepath = f"{log_folder}/{timestamp}_{trigger_reason}.jpg" 
        
        # 3. Multi-Monitor Capture
        img = ImageGrab.grab(all_screens=True)
        img = img.convert("RGB")
        
        # 4. Multi-Monitor virtual screen offset cursor drawing
        mx, my = mouse_pos
        try:
            left_offset = ctypes.windll.user32.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
            top_offset = ctypes.windll.user32.GetSystemMetrics(77)   # SM_YVIRTUALSCREEN
        except:
            left_offset = 0
            top_offset = 0
            
        mx = mx - left_offset
        my = my - top_offset
        
        cursor_points = [
            (mx, my), 
            (mx + (10 * CURSOR_SCALE), my + (15 * CURSOR_SCALE)), 
            (mx + (4 * CURSOR_SCALE), my + (15 * CURSOR_SCALE)), 
            (mx, my + (20 * CURSOR_SCALE))
        ]
        
        draw = ImageDraw.Draw(img)
        draw.polygon(cursor_points, fill="white", outline="black", width=1 * CURSOR_SCALE)
        
        img.save(filepath, format="JPEG", optimize=True, quality=30)
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO ActionLogs (timestamp, trigger_reason, file_path, app_name) 
            VALUES (?, ?, ?, ?)
        ''', (timestamp, trigger_reason, filepath, app_name))
        log_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        safe_print(f"Logged: [{app_name}] via {trigger_reason}")
        
        # 5. Launch Background WinRT OCR Thread
        ocr_worker = threading.Thread(target=run_ocr_in_background, args=(filepath, log_id))
        ocr_worker.start()
    finally:
        capture_lock.release()

def on_click(x, y, button, pressed):
    if pressed and not is_paused:
        current_app = get_active_window_title()
        worker = threading.Thread(target=capture_screen_in_background, args=("MouseClick", (x, y), current_app))
        worker.start()

def on_press(key):
    if is_paused:
        return
    target_keys = [keyboard.Key.enter, keyboard.Key.tab, keyboard.Key.esc]
    if key in target_keys:
        key_name = str(key).replace('Key.', '').capitalize()
        current_mouse_pos = pyautogui.position()
        current_app = get_active_window_title()
        worker = threading.Thread(target=capture_screen_in_background, args=(key_name, current_mouse_pos, current_app))
        worker.start()

# --- NEW: SYSTEM TRAY INTEGRATION LOGIC ---

def generate_tray_icon():
    """Generates the system tray icon, loading the professional logo if available."""
    try:
        project_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(project_dir, "logo.jpg")
        if os.path.exists(logo_path):
            return Image.open(logo_path).resize((32, 32))
    except:
        pass
    
    # Fallback high-visibility bright neon red icon
    image = Image.new('RGB', (32, 32), color=(255, 0, 50))
    draw = ImageDraw.Draw(image)
    draw.rectangle([8, 8, 24, 24], fill=(20, 20, 20))
    return image

def update_tray_menu(icon):
    """Rebuilds the menu instantly to display current state (Paused vs Running)."""
    status_text = "🟢 Running" if not is_paused else "🟡 Paused"
    pause_action_text = "Pause Recording" if not is_paused else "Resume Recording"
    
    icon.menu = pystray.Menu(
        pystray.MenuItem(status_text, lambda: None, enabled=False),
        pystray.MenuItem(pause_action_text, handle_pause_toggle),
        pystray.MenuItem("📂 Open History Viewer", handle_launch_viewer),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("❌ Exit BlackBox", handle_shutdown)
    )

def handle_pause_toggle(icon, item):
    global is_paused
    is_paused = not is_paused
    update_tray_menu(icon)

def handle_launch_viewer(icon, item):
    """Launches the viewer window correctly whether running as raw Python or a compiled EXE."""
    if os.path.exists("viewer.exe"):
        subprocess.Popen(["viewer.exe"], shell=True)
    else:
        subprocess.Popen(["python", "viewer.py"], shell=True)

def handle_shutdown(icon, item):
    """Stops the listeners and cleanly exits the system tray process."""
    icon.stop()
    mouse_listener.stop()
    keyboard_listener.stop()

def start_tray():
    global icon_instance, mouse_listener, keyboard_listener
    
    # Start capturing inputs asynchronously
    keyboard_listener = keyboard.Listener(on_press=on_press)
    mouse_listener = mouse.Listener(on_click=on_click)
    keyboard_listener.start()
    mouse_listener.start()
    
    # Build and initialize the Tray Icon object
    icon_instance = pystray.Icon("BlackBoxPC", generate_tray_icon(), "BlackBox PC")
    update_tray_menu(icon_instance)
    
    safe_print("BlackBox PC V5.3 (Stealth Mode) successfully active in System Tray.")
    icon_instance.run()

if __name__ == "__main__":
    start_tray()