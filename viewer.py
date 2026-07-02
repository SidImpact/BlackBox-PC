import customtkinter as ctk
import sqlite3
from PIL import Image, ImageTk
import os
import time
import threading
import calendar
import sys

DB_NAME = "blackbox_v5.db"  

# Set styling configurations
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class BlackBoxViewer(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("BlackBox PC — Visual History Viewer")
        self.geometry("1120x860")
        self.minsize(850, 650)
        
        self.logs = [] 
        self.tk_img = None
        self.current_pil_img = None
        self.current_index = -1
        self.last_size = (0, 0)
        
        # Zoom and Pan states
        self.zoom_scale = 1.0
        self.pan_offset_x = 0
        self.pan_offset_y = 0
        self.mouse_pressed_x = 0
        self.mouse_pressed_y = 0
        
        # Create Tab View Container
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill=ctk.BOTH, expand=True, padx=10, pady=5)
        
        self.tab_timeline = self.tabview.add("Timeline Viewer")
        self.tab_analytics = self.tabview.add("Productivity Analytics")
        self.tab_support = self.tabview.add("Support the Developer")
        
        # Configure Tab Bindings
        self.tabview.configure(command=self.on_tab_change)
        
        # --- TAB 1: TIMELINE CONTROLS LAYOUT ---
        # A. Top Search & Filter Panel Layout
        self.search_frame = ctk.CTkFrame(self.tab_timeline, fg_color="transparent")
        self.search_frame.pack(fill=ctk.X, side=ctk.TOP, padx=10, pady=(5, 5))
        
        self.search_label = ctk.CTkLabel(
            self.search_frame, 
            text="🔍 Filter:", 
            font=ctk.CTkFont(family="Arial", size=13, weight="bold")
        )
        self.search_label.pack(side=ctk.LEFT, padx=(0, 10))
        
        self.search_entry = ctk.CTkEntry(
            self.search_frame, 
            placeholder_text="Type search term to search window titles or OCR text...",
            font=ctk.CTkFont(family="Arial", size=13)
        )
        self.search_entry.pack(side=ctk.LEFT, fill=ctk.X, expand=True, padx=(0, 10))
        self.search_entry.bind("<KeyRelease>", lambda event: self.load_data())
        
        # Date Calendar Picker Button
        self.cal_toggle_btn = ctk.CTkButton(
            self.search_frame,
            text="📅 Date Picker",
            width=110,
            command=self.toggle_calendar,
            font=ctk.CTkFont(family="Arial", size=12, weight="bold")
        )
        self.cal_toggle_btn.pack(side=ctk.LEFT, padx=(0, 10))
        
        self.clear_btn = ctk.CTkButton(
            self.search_frame, 
            text="❌ Clear", 
            width=80,
            command=self.clear_search,
            font=ctk.CTkFont(family="Arial", size=12, weight="bold")
        )
        self.clear_btn.pack(side=ctk.RIGHT)
        
        # Calendar Collapsible Panel (Packed directly below search frame, hidden by default)
        self.calendar_panel = ctk.CTkFrame(self.tab_timeline, fg_color="#1e1e24", corner_radius=6)
        
        self.cal_ctrl_frame = ctk.CTkFrame(self.calendar_panel, fg_color="transparent")
        self.cal_ctrl_frame.pack(fill=ctk.X, padx=10, pady=5)
        
        # Month Selector
        self.cal_month_dropdown = ctk.CTkComboBox(
            self.cal_ctrl_frame,
            values=["January", "February", "March", "April", "May", "June", 
                    "July", "August", "September", "October", "November", "December"],
            width=120,
            command=lambda val: self.draw_calendar_grid()
        )
        self.cal_month_dropdown.pack(side=ctk.LEFT, padx=(0, 10))
        self.cal_month_dropdown.set("June")
        
        # Year Selector
        self.cal_year_dropdown = ctk.CTkComboBox(
            self.cal_ctrl_frame,
            values=["2025", "2026", "2027", "2028"],
            width=90,
            command=lambda val: self.draw_calendar_grid()
        )
        self.cal_year_dropdown.pack(side=ctk.LEFT)
        self.cal_year_dropdown.set("2026")
        
        # Day Buttons Frame
        self.calendar_days_frame = ctk.CTkFrame(self.calendar_panel, fg_color="transparent")
        self.calendar_days_frame.pack(padx=10, pady=(0, 10))
        
        # B. Bottom Control panel (packed first for proper layout stacking)
        self.control_panel = ctk.CTkFrame(self.tab_timeline, fg_color="transparent")
        self.control_panel.pack(fill=ctk.X, side=ctk.BOTTOM, padx=10, pady=(5, 5))
        
        self.status_label = ctk.CTkLabel(
            self.control_panel, 
            text="No data loaded", 
            font=ctk.CTkFont(family="Arial", size=13, weight="bold"), 
            text_color="#ecf0f1",
            anchor="w"
        )
        self.status_label.pack(fill=ctk.X, side=ctk.TOP, pady=(0, 4))
        
        # Activity Heatmap Canvas
        self.heatmap_canvas = ctk.CTkCanvas(self.control_panel, height=14, bg="#181822", highlightthickness=0)
        self.heatmap_canvas.pack(fill=ctk.X, pady=(0, 6))
        self.heatmap_canvas.bind("<Configure>", lambda event: self.draw_heatmap())
        
        # Timeline Range Slider Brackets Frame
        self.slider_frame = ctk.CTkFrame(self.control_panel, fg_color="transparent")
        self.slider_frame.pack(fill=ctk.X, side=ctk.TOP, pady=(0, 10))
        
        # Start Bracket Slider
        self.start_slider_frame = ctk.CTkFrame(self.slider_frame, fg_color="transparent")
        self.start_slider_frame.pack(fill=ctk.X, side=ctk.TOP, pady=1)
        self.start_label = ctk.CTkLabel(self.start_slider_frame, text="Start Frame: 1", width=120, anchor="w", font=ctk.CTkFont(size=11))
        self.start_label.pack(side=ctk.LEFT)
        self.start_slider = ctk.CTkSlider(self.start_slider_frame, from_=0, to=100, command=self.on_start_slide, progress_color="#e74c3c")
        self.start_slider.pack(fill=ctk.X, expand=True, side=ctk.LEFT, padx=10)
        self.start_slider.set(0)
        
        # End Bracket Slider
        self.end_slider_frame = ctk.CTkFrame(self.slider_frame, fg_color="transparent")
        self.end_slider_frame.pack(fill=ctk.X, side=ctk.TOP, pady=1)
        self.end_label = ctk.CTkLabel(self.end_slider_frame, text="End Frame: 100", width=120, anchor="w", font=ctk.CTkFont(size=11))
        self.end_label.pack(side=ctk.LEFT)
        self.end_slider = ctk.CTkSlider(self.end_slider_frame, from_=0, to=100, command=self.on_end_slide, progress_color="#3498db")
        self.end_slider.pack(fill=ctk.X, expand=True, side=ctk.LEFT, padx=10)
        self.end_slider.set(100)
        
        # Bottom Configurations Frame (Row 1)
        self.actions_frame = ctk.CTkFrame(self.control_panel, fg_color="transparent")
        self.actions_frame.pack(fill=ctk.X, side=ctk.TOP, pady=(0, 6))
        
        self.settings_label = ctk.CTkLabel(
            self.actions_frame, 
            text="⚙️ Auto-Clean History:", 
            font=ctk.CTkFont(family="Arial", size=12)
        )
        self.settings_label.pack(side=ctk.LEFT, padx=(0, 10))
        
        self.clean_dropdown = ctk.CTkComboBox(
            self.actions_frame, 
            values=["1 Day", "2 Days", "5 Days", "10 Days", "Never"], 
            state="readonly", 
            width=120,
            command=self.save_settings
        )
        self.clean_dropdown.pack(side=ctk.LEFT, padx=(0, 15))
        
        self.export_btn = ctk.CTkButton(
            self.actions_frame,
            text="🎞️ Export Slice Time-Lapse",
            width=180,
            fg_color="#27ae60",
            hover_color="#219653",
            command=self.export_timelapse,
            font=ctk.CTkFont(family="Arial", size=12, weight="bold")
        )
        self.export_btn.pack(side=ctk.LEFT)
        
        self.refresh_btn = ctk.CTkButton(
            self.actions_frame, 
            text="🔄 Refresh Data", 
            width=120,
            command=self.load_data,
            font=ctk.CTkFont(family="Arial", size=12, weight="bold")
        )
        self.refresh_btn.pack(side=ctk.RIGHT)
        
        # Privacy Blacklist Settings (Row 2)
        self.blacklist_frame = ctk.CTkFrame(self.control_panel, fg_color="transparent")
        self.blacklist_frame.pack(fill=ctk.X, side=ctk.TOP)
        
        self.blacklist_label = ctk.CTkLabel(
            self.blacklist_frame, 
            text="🚫 Privacy Blacklist (comma separated):", 
            font=ctk.CTkFont(family="Arial", size=12)
        )
        self.blacklist_label.pack(side=ctk.LEFT, padx=(0, 10))
        
        self.blacklist_entry = ctk.CTkEntry(
            self.blacklist_frame,
            placeholder_text="e.g. Bitwarden, Incognito, Banking",
            font=ctk.CTkFont(family="Arial", size=12)
        )
        self.blacklist_entry.pack(side=ctk.LEFT, fill=ctk.X, expand=True, padx=(0, 10))
        
        self.blacklist_save_btn = ctk.CTkButton(
            self.blacklist_frame,
            text="💾 Save",
            width=80,
            command=self.save_blacklist,
            font=ctk.CTkFont(family="Arial", size=12, weight="bold")
        )
        self.blacklist_save_btn.pack(side=ctk.RIGHT)
        
        # C. Central Visual Screenshot Panel (Standard tk.Canvas for zoom, pan, and OCR crop drawing)
        self.image_container = ctk.CTkFrame(self.tab_timeline, fg_color="#0e0e11", corner_radius=8)
        self.image_container.pack(fill=ctk.BOTH, expand=True, padx=10, pady=5)
        
        self.image_canvas = ctk.CTkCanvas(self.image_container, bg="#0b0b0e", highlightthickness=0)
        self.image_canvas.pack(fill=ctk.BOTH, expand=True, padx=5, pady=5)
        

        
        # Zoom & Pan Bindings
        self.image_canvas.bind("<MouseWheel>", self.zoom_image)
        self.image_canvas.bind("<ButtonPress-1>", self.start_pan)
        self.image_canvas.bind("<B1-Motion>", self.pan_image)
        
        # Crop Bounding Box OCR Bindings
        self.image_canvas.bind("<ButtonPress-3>", self.start_crop)
        self.image_canvas.bind("<B3-Motion>", self.draw_crop_rect)
        self.image_canvas.bind("<ButtonRelease-3>", self.end_crop)
        
        # --- TAB 2: PRODUCTIVITY ANALYTICS LAYOUT ---
        self.analytics_canvas = ctk.CTkCanvas(self.tab_analytics, bg="#111116", highlightthickness=0)
        self.analytics_canvas.pack(fill=ctk.BOTH, expand=True, padx=20, pady=20)
        self.tab_analytics.bind("<Configure>", lambda e: self.draw_analytics())
        
        # --- TAB 3: SUPPORT THE DEVELOPER LAYOUT ---
        self.support_container = ctk.CTkFrame(self.tab_support, fg_color="#181822", corner_radius=12)
        self.support_container.pack(fill=ctk.BOTH, expand=True, padx=40, pady=40)
        
        self.support_header = ctk.CTkLabel(
            self.support_container,
            text="💖 Support the Developer",
            font=ctk.CTkFont(family="Arial", size=24, weight="bold"),
            text_color="#f39c12"
        )
        self.support_header.pack(pady=(40, 20))
        
        self.support_desc = ctk.CTkLabel(
            self.support_container,
            text=(
                "BlackBox PC is completely open-source, local-first, and free of advertising.\n\n"
                "If this local time machine has saved your work, helped you recover lost information,\n"
                "or improved your daily productivity, please consider supporting the ongoing development\n"
                "to help keep the project maintained and updated!"
            ),
            font=ctk.CTkFont(family="Arial", size=14),
            text_color="#ecf0f1",
            justify="center"
        )
        self.support_desc.pack(pady=(0, 20))
        
        # Google Pay (GPay) UPI Copy Row
        self.upi_frame = ctk.CTkFrame(self.support_container, fg_color="#21212e", corner_radius=8, height=45)
        self.upi_frame.pack(fill=ctk.X, padx=80, pady=(0, 15))
        
        self.upi_label = ctk.CTkLabel(
            self.upi_frame, 
            text="💖 Google Pay (GPay) UPI ID:", 
            font=ctk.CTkFont(family="Arial", size=13, weight="bold"),
            text_color="#ecf0f1"
        )
        self.upi_label.pack(side=ctk.LEFT, padx=(20, 10), pady=10)
        
        self.upi_val_label = ctk.CTkLabel(
            self.upi_frame, 
            text="sidbhimgaj.s14@okaxis", 
            font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
            text_color="#2ecc71"
        )
        self.upi_val_label.pack(side=ctk.LEFT, padx=10, pady=10)
        
        def copy_upi():
            import pyperclip
            pyperclip.copy("sidbhimgaj.s14@okaxis")
            self.upi_copy_btn.configure(text="✅ Copied UPI!", fg_color="#27ae60")
            self.after(2000, lambda: self.upi_copy_btn.configure(text="📋 Copy ID", fg_color="#2980b9"))
            
        self.upi_copy_btn = ctk.CTkButton(
            self.upi_frame,
            text="📋 Copy ID",
            width=100,
            fg_color="#2980b9",
            hover_color="#3498db",
            font=ctk.CTkFont(family="Arial", size=12, weight="bold"),
            command=copy_upi
        )
        self.upi_copy_btn.pack(side=ctk.RIGHT, padx=(0, 20), pady=10)
        
        # Grid of other donation buttons
        self.buttons_container = ctk.CTkFrame(self.support_container, fg_color="transparent")
        self.buttons_container.pack(pady=10)
        
        import webbrowser
        
        # PayPal
        self.paypal_btn = ctk.CTkButton(
            self.buttons_container,
            text="💳 PayPal",
            width=220,
            height=40,
            fg_color="#00457c",
            hover_color="#003057",
            font=ctk.CTkFont(family="Arial", size=13, weight="bold"),
            command=lambda: webbrowser.open("https://PayPal.Me/siddharthSingh374")
        )
        self.paypal_btn.grid(row=0, column=0, padx=15, pady=8)
        
        # Ko-fi
        self.kofi_btn = ctk.CTkButton(
            self.buttons_container,
            text="🟢 Ko-fi",
            width=220,
            height=40,
            fg_color="#ff5e5b",
            hover_color="#d94b48",
            font=ctk.CTkFont(family="Arial", size=13, weight="bold"),
            command=lambda: webbrowser.open("https://ko-fi.com/sidimpact")
        )
        self.kofi_btn.grid(row=0, column=1, padx=15, pady=8)
        
        # Patreon
        self.patreon_btn = ctk.CTkButton(
            self.buttons_container,
            text="🟢 Patreon",
            width=220,
            height=40,
            fg_color="#f96854",
            hover_color="#d65645",
            font=ctk.CTkFont(family="Arial", size=13, weight="bold"),
            command=lambda: webbrowser.open("https://patreon.com/SIDDHARTHSINGH152?utm_medium=unknown&utm_source=join_link&utm_campaign=creatorshare_creator&utm_content=copyLink")
        )
        self.patreon_btn.grid(row=1, column=0, padx=15, pady=8)
        
        # Razorpay
        self.razorpay_btn = ctk.CTkButton(
            self.buttons_container,
            text="🟢 Razorpay",
            width=220,
            height=40,
            fg_color="#3399cc",
            hover_color="#247ba0",
            font=ctk.CTkFont(family="Arial", size=13, weight="bold"),
            command=lambda: webbrowser.open("https://razorpay.me/@siddharthsingh7719")
        )
        self.razorpay_btn.grid(row=1, column=1, padx=15, pady=8)
        
        # Chai4.me
        self.chai_btn = ctk.CTkButton(
            self.buttons_container,
            text="🟢 Chai4.me",
            width=220,
            height=40,
            fg_color="#d35400",
            hover_color="#b33900",
            font=ctk.CTkFont(family="Arial", size=13, weight="bold"),
            command=lambda: webbrowser.open("https://www.chai4.me/sidbhimgajs14gmailcom")
        )
        self.chai_btn.grid(row=2, column=0, columnspan=2, padx=15, pady=8)
        

        
        # Initialization
        self.set_window_icon()
        self.setup_database()
        self.load_settings()
        self.load_blacklist_setting()
        self.load_data()
        self.draw_calendar_grid()

    def set_window_icon(self):
        try:
            project_dir = os.path.dirname(os.path.abspath(__file__))
            logo_path = os.path.join(project_dir, "logo.jpg")
            if os.path.exists(logo_path):
                img = Image.open(logo_path)
                self.icon_photo = ImageTk.PhotoImage(img.resize((64, 64)))
                self.iconphoto(False, self.icon_photo)
        except:
            pass

    def setup_database(self):
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
        
        cursor.execute("PRAGMA table_info(ActionLogs)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'ocr_text' not in columns:
            cursor.execute("ALTER TABLE ActionLogs ADD COLUMN ocr_text TEXT")
            
        conn.commit()
        conn.close()

    def clear_search(self):
        self.search_entry.delete(0, 'end')
        self.load_data()

    def load_settings(self):
        if not os.path.exists(DB_NAME):
            self.clean_dropdown.set("Never")
            return
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM Settings WHERE key = 'retention'")
        result = cursor.fetchone()
        current_setting = result[0] if result else "Never"
        self.clean_dropdown.set(current_setting)
        conn.close()

    def save_settings(self, selected_option):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO Settings (key, value) VALUES ('retention', ?) ", (selected_option,))
        conn.commit()
        conn.close()
        self.status_label.configure(text=f"✅ Saved Preference! Auto-Clean set to: {selected_option}")

    def load_blacklist_setting(self):
        if not os.path.exists(DB_NAME):
            return
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM Settings WHERE key = 'blacklist'")
        result = cursor.fetchone()
        current_blacklist = result[0] if result else "1Password, Bitwarden, Incognito, Online Banking"
        self.blacklist_entry.delete(0, 'end')
        self.blacklist_entry.insert(0, current_blacklist)
        conn.close()

    def save_blacklist(self):
        blacklist_text = self.blacklist_entry.get().strip()
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO Settings (key, value) VALUES ('blacklist', ?) ", (blacklist_text,))
        conn.commit()
        conn.close()
        self.status_label.configure(text="✅ Saved Preference! Privacy blacklist updated.")

    def toggle_calendar(self):
        if self.calendar_panel.winfo_manager():
            self.calendar_panel.pack_forget()
        else:
            self.calendar_panel.pack(fill=ctk.X, side=ctk.TOP, after=self.search_frame, padx=20, pady=5)
            self.draw_calendar_grid()

    def draw_calendar_grid(self):
        for widget in self.calendar_days_frame.winfo_children():
            widget.destroy()
            
        year = int(self.cal_year_dropdown.get())
        months = ["January", "February", "March", "April", "May", "June", 
                  "July", "August", "September", "October", "November", "December"]
        month_str = self.cal_month_dropdown.get()
        month = months.index(month_str) + 1
        
        # Draw header labels
        weekdays = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
        for col, day_name in enumerate(weekdays):
            lbl = ctk.CTkLabel(
                self.calendar_days_frame, 
                text=day_name, 
                font=ctk.CTkFont(family="Arial", size=11, weight="bold"), 
                width=35
            )
            lbl.grid(row=0, column=col, padx=2, pady=1)
            
        cal = calendar.monthcalendar(year, month)
        for r, week in enumerate(cal):
            for col, day in enumerate(week):
                if day != 0:
                    btn = ctk.CTkButton(
                        self.calendar_days_frame, 
                        text=str(day), 
                        width=35, 
                        height=25,
                        fg_color="#2c3e50",
                        hover_color="#16a085",
                        font=ctk.CTkFont(family="Arial", size=10),
                        command=lambda d=day, m=month, y=year: self.filter_by_date(y, m, d)
                    )
                    btn.grid(row=r+1, column=col, padx=2, pady=2)

    def filter_by_date(self, year, month, day):
        date_str = f"{year:04d}-{month:02d}-{day:02d}"
        self.search_entry.delete(0, 'end')
        self.search_entry.insert(0, date_str)
        self.load_data()
        self.toggle_calendar()

    def get_category(self, app_name):
        app_name_lower = app_name.lower()
        if any(x in app_name_lower for x in ["code", "pycharm", "visual studio", "terminal", "cmd", "powershell", "git", "github", "sublime", "notepad++"]):
            return "Development"
        elif any(x in app_name_lower for x in ["chrome", "edge", "firefox", "opera", "safari", "brave", "browser"]):
            return "Browsing"
        elif any(x in app_name_lower for x in ["slack", "discord", "teams", "whatsapp", "zoom", "skype", "telegram", "messenger"]):
            return "Communication"
        elif any(x in app_name_lower for x in ["word", "excel", "powerpoint", "pdf", "acrobat", "notepad", "text", "read me"]):
            return "Documents"
        else:
            return "Other"

    def draw_heatmap(self):
        self.heatmap_canvas.delete("all")
        if not self.logs:
            return
        
        total_logs = len(self.logs)
        self.update_idletasks()
        width = self.heatmap_canvas.winfo_width()
        if width <= 1:
            width = 1000
            
        segment_width = width / total_logs
        color_map = {
            "Development": "#2ecc71",
            "Browsing": "#3498db",
            "Communication": "#9b59b6",
            "Documents": "#e67e22",
            "Other": "#4f5d65"
        }
        
        for i, log in enumerate(self.logs):
            app_name = log[3]
            cat = self.get_category(app_name)
            color = color_map.get(cat, "#4f5d65")
            
            x0 = i * segment_width
            x1 = (i + 1) * segment_width
            self.heatmap_canvas.create_rectangle(x0, 0, x1, 14, fill=color, outline="")

    def load_data(self):
        if not os.path.exists(DB_NAME):
            self.status_label.configure(text="Database file not found yet! Record actions first.")
            return
            
        search_query = self.search_entry.get().strip()
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        if search_query:
            cleaned_timestamp = search_query.replace("-", "").replace(":", "").replace("/", "").replace(" ", "")
            query = '''
                SELECT timestamp, trigger_reason, file_path, app_name 
                FROM ActionLogs 
                WHERE app_name LIKE ? 
                   OR trigger_reason LIKE ? 
                   OR timestamp LIKE ?
                   OR ocr_text LIKE ?
                ORDER BY id ASC
            '''
            like_term = f"%{search_query}%"
            like_timestamp = f"%{cleaned_timestamp}%"
            cursor.execute(query, (like_term, like_term, like_timestamp, like_term))
        else:
            cursor.execute("SELECT timestamp, trigger_reason, file_path, app_name FROM ActionLogs ORDER BY id ASC")
            
        self.logs = cursor.fetchall()
        conn.close()
        
        self.draw_heatmap()
        
        if self.logs:
            total_frames = len(self.logs)
            
            if total_frames > 1:
                # Configure start slider
                self.start_slider.configure(from_=0, to=total_frames - 1, number_of_steps=total_frames - 1, state="normal")
                self.start_slider.set(0)
                self.start_label.configure(text="Start Frame: 1")
                
                # Configure end slider
                self.end_slider.configure(from_=0, to=total_frames - 1, number_of_steps=total_frames - 1, state="normal")
                self.end_slider.set(total_frames - 1)
                self.end_label.configure(text=f"End Frame: {total_frames}")
            else:
                # Fallback for exactly 1 frame
                self.start_slider.configure(from_=0, to=1, number_of_steps=1, state="disabled")
                self.start_slider.set(0)
                self.start_label.configure(text="Start Frame: 1")
                
                self.end_slider.configure(from_=0, to=1, number_of_steps=1, state="disabled")
                self.end_slider.set(0)
                self.end_label.configure(text="End Frame: 1")
                
            self.current_index = total_frames - 1
            self.show_frame(total_frames - 1)
        else:
            # Fallback for 0 frames
            self.start_slider.configure(from_=0, to=1, number_of_steps=1, state="disabled")
            self.start_slider.set(0)
            self.start_label.configure(text="Start Frame: --")
            
            self.end_slider.configure(from_=0, to=1, number_of_steps=1, state="disabled")
            self.end_slider.set(0)
            self.end_label.configure(text="End Frame: --")
            self.current_index = -1
            self.status_label.configure(text="🔍 No matching logs found. Try another search keyword!")
            self.image_canvas.delete("all")
            self.image_canvas.create_text(
                450, 200, 
                text="No matching visual history records.", 
                fill="#7f8c8d", 
                font=("Arial", 14)
            )

    def show_frame(self, index):
        index = int(float(index)) 
        if not self.logs or index < 0 or index >= len(self.logs):
            return
        
        self.current_index = index
        timestamp, trigger, file_path, app_name = self.logs[index]
        formatted_time = f"{timestamp[0:4]}-{timestamp[4:6]}-{timestamp[6:8]} {timestamp[9:11]}:{timestamp[11:13]}:{timestamp[13:15]}"
        
        self.status_label.configure(
            text=f"🕒 Time: {formatted_time}  |  🎬 Action: {trigger}  |  🖥️ App: {app_name} ({index + 1}/{len(self.logs)})"
        )
        
        if os.path.exists(file_path):
            try:
                self.current_pil_img = Image.open(file_path)
                self.redraw_image()
            except Exception as e:
                self.image_canvas.delete("all")
                self.image_canvas.create_text(
                    450, 200, 
                    text=f"Error loading image: {e}", 
                    fill="#e74c3c", 
                    font=("Arial", 14)
                )
        else:
            self.image_canvas.delete("all")
            self.image_canvas.create_text(
                450, 200, 
                text=f"Missing image file: {file_path}", 
                fill="#e74c3c", 
                font=("Arial", 14)
            )

    def redraw_image(self):
        if not hasattr(self, "current_pil_img") or not self.current_pil_img:
            return
            
        canvas_w = self.image_canvas.winfo_width()
        canvas_h = self.image_canvas.winfo_height()
        if canvas_w <= 1 or canvas_h <= 1:
            canvas_w, canvas_h = 950, 500
            
        img_w, img_h = self.current_pil_img.size
        fit_ratio = min(canvas_w / img_w, canvas_h / img_h)
        
        scaled_w = max(int(img_w * fit_ratio * self.zoom_scale), 10)
        scaled_h = max(int(img_h * fit_ratio * self.zoom_scale), 10)
        
        resized_img = self.current_pil_img.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)
        self.tk_img = ImageTk.PhotoImage(resized_img)
        
        self.image_canvas.delete("image")
        
        center_x = (canvas_w / 2) + self.pan_offset_x
        center_y = (canvas_h / 2) + self.pan_offset_y
        
        self.image_canvas.create_image(center_x, center_y, anchor="center", image=self.tk_img, tags="image")
        self.image_canvas.image = self.tk_img

    def zoom_image(self, event):
        if not hasattr(self, "current_pil_img") or not self.current_pil_img:
            return
        factor = 1.15 if event.delta > 0 else 0.85
        new_scale = self.zoom_scale * factor
        if 0.15 <= new_scale <= 12.0:
            self.zoom_scale = new_scale
            self.pan_offset_x = int(self.pan_offset_x * factor)
            self.pan_offset_y = int(self.pan_offset_y * factor)
            self.redraw_image()

    def start_pan(self, event):
        self.mouse_pressed_x = event.x
        self.mouse_pressed_y = event.y
        self.start_pan_offset_x = self.pan_offset_x
        self.start_pan_offset_y = self.pan_offset_y

    def pan_image(self, event):
        dx = event.x - self.mouse_pressed_x
        dy = event.y - self.mouse_pressed_y
        self.pan_offset_x = self.start_pan_offset_x + dx
        self.pan_offset_y = self.start_pan_offset_y + dy
        self.redraw_image()

    def start_crop(self, event):
        self.crop_start_x = event.x
        self.crop_start_y = event.y
        self.image_canvas.delete("crop_rect")

    def draw_crop_rect(self, event):
        self.image_canvas.delete("crop_rect")
        self.image_canvas.create_rectangle(
            self.crop_start_x, self.crop_start_y, event.x, event.y,
            outline="#e74c3c", width=2, dash=(4, 4), tags="crop_rect"
        )

    def end_crop(self, event):
        self.image_canvas.delete("crop_rect")
        if not hasattr(self, "current_pil_img") or not self.current_pil_img:
            return
            
        crop_end_x = event.x
        crop_end_y = event.y
        
        canvas_w = self.image_canvas.winfo_width()
        canvas_h = self.image_canvas.winfo_height()
        
        img_w, img_h = self.current_pil_img.size
        fit_ratio = min(canvas_w / img_w, canvas_h / img_h)
        
        scaled_w = int(img_w * fit_ratio * self.zoom_scale)
        scaled_h = int(img_h * fit_ratio * self.zoom_scale)
        
        center_x = (canvas_w / 2) + self.pan_offset_x
        center_y = (canvas_h / 2) + self.pan_offset_y
        
        img_left = center_x - (scaled_w / 2)
        img_top = center_y - (scaled_h / 2)
        
        sel_x0 = min(self.crop_start_x, crop_end_x) - img_left
        sel_y0 = min(self.crop_start_y, crop_end_y) - img_top
        sel_x1 = max(self.crop_start_x, crop_end_x) - img_left
        sel_y1 = max(self.crop_start_y, crop_end_y) - img_top
        
        sel_x0 = max(0, min(sel_x0, scaled_w))
        sel_y0 = max(0, min(sel_y0, scaled_h))
        sel_x1 = max(0, min(sel_x1, scaled_w))
        sel_y1 = max(0, min(sel_y1, scaled_h))
        
        if (sel_x1 - sel_x0 < 5) or (sel_y1 - sel_y0 < 5):
            return
            
        scale_factor = img_w / scaled_w
        pil_x0 = int(sel_x0 * scale_factor)
        pil_y0 = int(sel_y0 * scale_factor)
        pil_x1 = int(sel_x1 * scale_factor)
        pil_y1 = int(sel_y1 * scale_factor)
        
        cropped_pil = self.current_pil_img.crop((pil_x0, pil_y0, pil_x1, pil_y1))
        
        def run_crop_ocr():
            try:
                temp_path = "temp_crop.png"
                cropped_pil.save(temp_path, format="PNG")
                
                import asyncio
                import winrt.windows.storage as wstorage
                import winrt.windows.media.ocr as wocr
                import winrt.windows.graphics.imaging as wimaging
                import pyperclip
                
                async def run_async():
                    abs_path = os.path.abspath(temp_path)
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
                        ocr_text = result.text.strip()
                        if ocr_text:
                            pyperclip.copy(ocr_text)
                            self.status_label.configure(text=f"📋 Text Copied! Context: \"{ocr_text[:60]}...\"")
                        else:
                            self.status_label.configure(text="🔍 OCR Warning: No text identified in selection box.")
                    else:
                        self.status_label.configure(text="❌ OCR Engine failed to load.")
                        
                asyncio.run(run_async())
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception as e:
                self.status_label.configure(text=f"❌ Crop OCR Failed: {e}")
                
        threading.Thread(target=run_crop_ocr).start()

    def on_start_slide(self, value):
        val = int(float(value))
        end_val = int(float(self.end_slider.get()))
        if val > end_val:
            self.start_slider.set(end_val)
            val = end_val
        self.start_label.configure(text=f"Start Frame: {val + 1}")
        self.show_frame(val)

    def on_end_slide(self, value):
        val = int(float(value))
        start_val = int(float(self.start_slider.get()))
        if val < start_val:
            self.end_slider.set(start_val)
            val = start_val
        self.end_label.configure(text=f"End Frame: {val + 1}")
        self.show_frame(val)

    def on_tab_change(self):
        current_tab = self.tabview.get()
        if current_tab == "Productivity Analytics":
            self.draw_analytics()

    def draw_analytics(self):
        self.analytics_canvas.delete("all")
        if not self.logs:
            self.analytics_canvas.create_text(
                350, 150, 
                text="No logs loaded to analyze. Record actions first!", 
                fill="#7f8c8d", 
                font=("Arial", 14)
            )
            return
            
        counts = {"Development": 0, "Browsing": 0, "Communication": 0, "Documents": 0, "Other": 0}
        for log in self.logs:
            cat = self.get_category(log[3])
            counts[cat] = counts.get(cat, 0) + 1
            
        total = sum(counts.values())
        color_map = {
            "Development": "#2ecc71",
            "Browsing": "#3498db",
            "Communication": "#9b59b6",
            "Documents": "#e67e22",
            "Other": "#7f8c8d"
        }
        
        self.update_idletasks()
        c_w = self.analytics_canvas.winfo_width()
        if c_w <= 1: 
            c_w = 700
            
        self.analytics_canvas.create_text(
            15, 25, 
            anchor="w", 
            text=f"📊 Productivity Summary (Based on {total} Filtered Logs):", 
            fill="#ffffff", 
            font=("Arial", 14, "bold")
        )
        
        y = 70
        for cat, count in counts.items():
            percentage = (count / total) * 100
            color = color_map[cat]
            
            # Draw labels
            self.analytics_canvas.create_text(
                15, y + 10, 
                anchor="w", 
                text=f"{cat} ({percentage:.1f}%)", 
                fill="#ecf0f1", 
                font=("Arial", 12, "bold")
            )
            
            # Progress bar background
            self.analytics_canvas.create_rectangle(180, y, c_w - 40, y + 20, fill="#2c3e50", outline="")
            
            # Progress bar representation
            bar_max_w = (c_w - 40) - 180
            bar_w = int(bar_max_w * (percentage / 100))
            if bar_w > 0:
                self.analytics_canvas.create_rectangle(180, y, 180 + bar_w, y + 20, fill=color, outline="")
                
            y += 50

    def on_window_resize(self, event):
        if event.widget == self:
            width = event.width
            height = event.height
            if self.last_size != (width, height):
                self.last_size = (width, height)
                self.draw_heatmap()
                if self.current_index != -1:
                    self.show_frame(self.current_index)

    def export_timelapse(self):
        """Compiles and exports selected slider range of frames as video/GIF."""
        if not self.logs:
            self.status_label.configure(text="❌ No frames available to export!")
            return
            
        start_idx = int(float(self.start_slider.get()))
        end_idx = int(float(self.end_slider.get()))
        
        if start_idx > end_idx:
            start_idx, end_idx = end_idx, start_idx
            
        selected_logs = self.logs[start_idx:end_idx + 1]
        
        if not selected_logs:
            self.status_label.configure(text="❌ Invalid frame slice range.")
            return
            
        from tkinter import filedialog, messagebox
        
        file_path = filedialog.asksaveasfilename(
            title="Save Time-Lapse",
            defaultextension=".mp4",
            filetypes=[("MP4 Video", "*.mp4"), ("Animated GIF", "*.gif")]
        )
        
        if not file_path:
            return
            
        self.status_label.configure(text="🎬 Compiling time-lapse video... please wait.")
        
        def worker():
            try:
                import imageio
                import numpy as np
                
                is_gif = file_path.lower().endswith(".gif")
                image_files = [log[2] for log in selected_logs if os.path.exists(log[2])]
                
                if not image_files:
                    self.status_label.configure(text="❌ Error: All screenshot files in this slice are missing on disk.")
                    return
                    
                if is_gif:
                    with imageio.get_writer(file_path, mode='I', duration=0.5) as writer:
                        for f in image_files:
                            img = Image.open(f)
                            img.thumbnail((800, 450))
                            writer.append_data(np.array(img))
                else:
                    with imageio.get_writer(file_path, fps=2) as writer:
                        for f in image_files:
                            img = Image.open(f)
                            img.thumbnail((1280, 720))
                            # Dimensions must be divisible by 2 for FFMPEG encoder
                            w, h = img.size
                            if w % 2 != 0: w -= 1
                            if h % 2 != 0: h -= 1
                            img = img.resize((w, h))
                            writer.append_data(np.array(img))
                            
                self.status_label.configure(text=f"🎉 Success! Exported time-lapse containing {len(image_files)} frames.")
                messagebox.showinfo("Export Success", f"Time-lapse video successfully created!\nFrames: {len(image_files)}\nSaved to: {file_path}")
            except Exception as e:
                self.status_label.configure(text=f"❌ Export Failed: {e}")
                messagebox.showerror("Export Error", f"Failed to export time-lapse:\n{e}")
                
        threading.Thread(target=worker).start()

if __name__ == "__main__":
    app = BlackBoxViewer()
    app.mainloop()