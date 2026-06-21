import tkinter as tk
from tkinter import ttk
import sqlite3
from PIL import Image, ImageTk
import os

DB_NAME = "blackbox_v5.db"  

class BlackBoxViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("BlackBox PC — Visual History Viewer")
        self.root.geometry("1000x800") 
        
        self.logs = [] 
        
        # NEW: Top Search Panel Layout
        search_frame = tk.Frame(root, pady=8)
        search_frame.pack(fill=tk.X, side=tk.TOP, padx=10)
        
        search_label = tk.Label(search_frame, text="🔍 Live Filter (App, Action, Date or Time):", font=("Arial", 9, "bold"))
        search_label.pack(side=tk.LEFT, padx=(0, 5))
        
        self.search_entry = tk.Entry(search_frame, font=("Arial", 10))
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        # Bind key releases to instantly run the database search filter as you type!
        self.search_entry.bind("<KeyRelease>", lambda event: self.load_data())
        
        self.clear_btn = tk.Button(search_frame, text="❌ Clear", command=self.clear_search, padx=8)
        self.clear_btn.pack(side=tk.RIGHT)
        
        # Central Visual Screen Panel
        self.image_label = tk.Label(root, text="Click 'Refresh' to load your history", bg="black", fg="white")
        self.image_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Bottom Dashboard Controls Panel
        control_panel = tk.Frame(root)
        control_panel.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=10)
        
        self.status_label = tk.Label(control_panel, text="No data loaded", font=("Arial", 10, "bold"), fg="#333333")
        self.status_label.pack(anchor=tk.W, pady=(0, 5))
        
        # Timeline Slider Configuration
        self.slider = ttk.Scale(control_panel, from_=0, to=100, orient=tk.HORIZONTAL, command=self.on_slide)
        self.slider.pack(fill=tk.X, expand=True, side=tk.TOP, pady=(0, 10))
        
        # Bottom Actions Sub-Frame
        actions_frame = tk.Frame(control_panel)
        actions_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        settings_label = tk.Label(actions_frame, text="⚙️ Auto-Clean History Older Than:", font=("Arial", 9))
        settings_label.pack(side=tk.LEFT, padx=(0, 5))
        
        self.clean_dropdown = ttk.Combobox(
            actions_frame, 
            values=["1 Day", "2 Days", "5 Days", "10 Days", "Never"], 
            state="readonly", 
            width=10
        )
        self.clean_dropdown.pack(side=tk.LEFT)
        self.clean_dropdown.bind("<<ComboboxSelected>>", self.save_settings)
        
        self.refresh_btn = tk.Button(actions_frame, text="🔄 Refresh Data", command=self.load_data, padx=5, pady=2)
        self.refresh_btn.pack(side=tk.RIGHT)
        
        # Initialization
        self.load_settings()
        self.load_data()

    def clear_search(self):
        """Clears text inside the search bar and reloads complete raw logs."""
        self.search_entry.delete(0, tk.END)
        self.load_data()

    def load_settings(self):
        if not os.path.exists(DB_NAME):
            self.clean_dropdown.set("Never")
            return
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS Settings (key TEXT PRIMARY KEY, value TEXT)")
        cursor.execute("SELECT value FROM Settings WHERE key = 'retention'")
        result = cursor.fetchone()
        current_setting = result[0] if result else "Never"
        self.clean_dropdown.set(current_setting)
        conn.close()

    def save_settings(self, event):
        selected_option = self.clean_dropdown.get()
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO Settings (key, value) VALUES ('retention', ?) ", (selected_option,))
        conn.commit()
        conn.close()
        self.status_label.config(text=f"✅ Saved Preference! Auto-Clean set to: {selected_option}")

    def load_data(self):
        if not os.path.exists(DB_NAME):
            self.status_label.config(text="Database file not found yet! Record actions first.")
            return
            
        # Extract live text from search entry widget
        search_query = self.search_entry.get().strip()
            
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        if search_query:
            # UPGRADED: Normalize common formatting characters to support dates/times
            # Example: '2026-06-19' or '22:23' becomes '20260619' or '2223' to match SQL layout
            cleaned_timestamp = search_query.replace("-", "").replace(":", "").replace("/", "").replace(" ", "")
            
            query = '''
                SELECT timestamp, trigger_reason, file_path, app_name 
                FROM ActionLogs 
                WHERE app_name LIKE ? 
                   OR trigger_reason LIKE ? 
                   OR timestamp LIKE ?
                ORDER BY id ASC
            '''
            like_term = f"%{search_query}%"
            like_timestamp = f"%{cleaned_timestamp}%"
            cursor.execute(query, (like_term, like_term, like_timestamp))
        else:
            cursor.execute("SELECT timestamp, trigger_reason, file_path, app_name FROM ActionLogs ORDER BY id ASC")
            
        self.logs = cursor.fetchall()
        conn.close()
        
        if self.logs:
            total_frames = len(self.logs)
            self.slider.config(from_=0, to=total_frames - 1)
            # Instantly match slider position to the newest filtered index frame
            self.slider.set(total_frames - 1) 
            self.show_frame(total_frames - 1)
        else:
            # Safe Fallback: Handle situations where search query yields zero matches
            self.slider.config(from_=0, to=0)
            self.slider.set(0)
            self.status_label.config(text="🔍 No matching logs found. Try another search keyword!")
            self.image_label.config(image="", text="No matching visual history records.")

    def show_frame(self, index):
        index = int(float(index)) 
        if not self.logs or index < 0 or index >= len(self.logs):
            return
            
        timestamp, trigger, file_path, app_name = self.logs[index]
        formatted_time = f"{timestamp[0:4]}-{timestamp[4:6]}-{timestamp[6:8]} {timestamp[9:11]}:{timestamp[11:13]}:{timestamp[13:15]}"
        
        self.status_label.config(
            text=f"🕒 Time: {formatted_time}  |  🎬 Action: {trigger}  |  🖥️ App: {app_name} ({index + 1}/{len(self.logs)})"
        )
        
        if os.path.exists(file_path):
            try:
                img = Image.open(file_path)
                window_width = self.root.winfo_width() - 40
                window_height = self.root.winfo_height() - 210  # Adjusted offset for extra top search bar space
                width = window_width if window_width > 100 else 950
                height = window_height if window_height > 100 else 550
                
                img.thumbnail((width, height))
                self.tk_img = ImageTk.PhotoImage(img)
                self.image_label.config(image=self.tk_img, text="")
            except Exception as e:
                self.image_label.config(image="", text=f"Error loading image: {e}")
        else:
            self.image_label.config(image="", text=f"Missing image file: {file_path}")

    def on_slide(self, value):
        self.show_frame(value)

if __name__ == "__main__":
    root = tk.Tk()
    app = BlackBoxViewer(root)
    root.mainloop()