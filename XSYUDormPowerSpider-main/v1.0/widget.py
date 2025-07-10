import tkinter as tk
from tkinter import Menu, messagebox
import threading
import time
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import subprocess
import sys
from database import DatabaseManager
from utils import open_main_app, open_recharge_page
import platform
from datetime import datetime
import pystray
from PIL import Image, ImageDraw, ImageFont
import re

from config import ConfigManager
from scraper import Scraper

class PowerWidget:
    def __init__(self, dorm_id, dorm_type, dorm_name):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)

        self.config_manager = ConfigManager()
        self.db_manager = DatabaseManager()
        self.scraper = Scraper()
        
        self.dorm_id = dorm_id
        self.dorm_type = dorm_type
        self.dorm_name = dorm_name

        # Correctly read the 'Widget' section for the style
        self.style_name = self.config_manager.get_setting('Widget', 'style', '默认')
        
        self.setup_transparency()

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        widget_width = 180
        widget_height = 120
        x_position = screen_width - widget_width - 20
        y_position = screen_height - widget_height - 40
        self.root.geometry(f"{widget_width}x{widget_height}+{x_position}+{y_position}")

        self.setup_colors()
        self.create_ui_elements()

        self.x = 0
        self.y = 0

        self.update_power()
        self.bind_events()
        self.animate_in()

        self.tray_icon = None
        self.is_visible = True
        self.setup_tray_icon()
        self._check_events()

    def setup_colors(self):
        if self.style_name == '猫娘':
            self.colors = {
                'bg': '#FFEFF5', 'fg': '#6D4A5A', 'low': '#FF7A9E',
                'medium': '#FFB6C1', 'high': '#FF87AB', 'outline': '#FFC0CB', 'icon': '#FFFFFF'
            }
        else: # Default style
            self.colors = {
                'bg': '#FFFFFF', 'fg': '#333333', 'low': '#e06666',
                'medium': '#f6b26b', 'high': '#4a86e8', 'outline': '#dddddd', 'icon': '#4a86e8'
            }

    def setup_transparency(self):
        current_platform = platform.system()
        try:
            # Use a background color that is unlikely to be used, for transparency key
            transparent_color = '#abcdef'
            self.root.config(bg=transparent_color)
            if current_platform == "Windows":
                self.root.attributes('-transparentcolor', transparent_color)
            elif current_platform == "Darwin": # macOS
                self.root.wm_attributes("-transparent", True)
                self.root.config(bg='systemTransparent')
        except tk.TclError:
             pass # Ignore if transparency is not supported

    def create_ui_elements(self):
        self.canvas = tk.Canvas(self.root, width=180, height=120, bg=self.root.cget('bg'), highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.create_rounded_background()

        if self.style_name == '猫娘':
            self.create_cat_ears()

        self.create_power_icon()

        self.name_label = tk.Label(self.canvas, text=self.dorm_name, bg=self.colors['bg'], font=("微软雅黑", 10, "bold"), fg=self.colors['fg'])
        self.canvas.create_window(90, 20, window=self.name_label)
        self.power_label = tk.Label(self.canvas, text="加载中...", bg=self.colors['bg'], font=("微软雅黑", 28, "bold"), fg=self.colors['fg'])
        self.canvas.create_window(90, 60, window=self.power_label)
        self.time_label = tk.Label(self.canvas, text="", bg=self.colors['bg'], font=("微软雅黑", 8), fg=self.colors['fg'])
        self.canvas.create_window(90, 95, window=self.time_label)

    def create_rounded_background(self):
        radius = 20
        self.canvas.create_oval(5, 5, 5+radius, 5+radius, fill=self.colors['bg'], outline=self.colors['outline'])
        self.canvas.create_oval(175-radius, 5, 175, 5+radius, fill=self.colors['bg'], outline=self.colors['outline'])
        self.canvas.create_oval(5, 115-radius, 5+radius, 115, fill=self.colors['bg'], outline=self.colors['outline'])
        self.canvas.create_oval(175-radius, 115-radius, 175, 115, fill=self.colors['bg'], outline=self.colors['outline'])
        self.canvas.create_rectangle(5+radius/2, 5, 175-radius/2, 115, fill=self.colors['bg'], width=0)
        self.canvas.create_rectangle(5, 5+radius/2, 175, 115-radius/2, fill=self.colors['bg'], width=0)

    def create_cat_ears(self):
        self.canvas.create_polygon(15, 20, 45, 5, 45, 25, fill=self.colors['bg'], outline=self.colors['outline'], width=1)
        self.canvas.create_polygon(165, 20, 135, 5, 135, 25, fill=self.colors['bg'], outline=self.colors['outline'], width=1)

    def create_power_icon(self):
        icon_x, icon_y, icon_size = 40, 60, 15
        if self.style_name == '猫娘':
            points = [icon_x, icon_y, icon_x+icon_size/4, icon_y-icon_size/2, icon_x+icon_size/2, icon_y-icon_size/3, icon_x+icon_size/4, icon_y, icon_x, icon_y+icon_size/2, icon_x-icon_size/4, icon_y, icon_x-icon_size/2, icon_y-icon_size/3, icon_x-icon_size/4, icon_y-icon_size/2]
        else: # Default lightning bolt
            points = [icon_x, icon_y-icon_size, icon_x+icon_size/2, icon_y, icon_x, icon_y+icon_size, icon_x-icon_size/2, icon_y]
        self.power_icon = self.canvas.create_polygon(points, fill=self.colors['icon'], outline=self.colors['outline'], width=1)
    
    def bind_events(self):
        self.root.bind("<Button-1>", self.start_drag)
        self.root.bind("<B1-Motion>", self.on_drag)
        self.root.bind("<Button-3>", self.show_menu)
        self.root.bind("<Double-1>", self.toggle_visibility)

    def start_drag(self, event):
        self.x, self.y = event.x, event.y

    def on_drag(self, event):
        new_x = self.root.winfo_x() + event.x - self.x
        new_y = self.root.winfo_y() + event.y - self.y
        self.root.geometry(f"+{new_x}+{new_y}")
    
    def show_menu(self, event):
        menu = Menu(self.root, tearoff=0)
        menu.add_command(label="显示/隐藏", command=self.toggle_visibility)
        menu.add_command(label="切换宿舍", command=self.switch_dormitory)
        menu.add_command(label="前往充值", command=lambda: open_recharge_page(self.dorm_id, self.dorm_type))
        menu.add_command(label="查看电量变化(主程序)", command=open_main_app)
        menu.add_separator()
        menu.add_command(label="退出", command=self.quit_application)
        menu.post(event.x_root, event.y_root)

    def toggle_visibility(self, event=None):
        if self.is_visible: self.hide_window()
        else: self.show_window()

    def hide_window(self):
        self.root.withdraw(); self.is_visible = False
        if self.tray_icon: self.tray_icon.update_menu()

    def show_window(self):
        self.root.deiconify(); self.is_visible = True
        if self.tray_icon: self.tray_icon.update_menu()

    def switch_dormitory(self):
        self.quit_application()
        open_main_app()

    def update_power(self):
        threading.Thread(target=self.fetch_power, daemon=True).start()
        self.root.after(1800000, self.update_power) # Update every 30 minutes

    def fetch_power(self):
        power_text, error_message = self.scraper.get_power(self.dorm_id, self.dorm_type)
        if not self.root: return
        
        if error_message:
            return self.root.after(0, self.update_display, "获取失败", "请检查网络", False)
        
        try:
            match = re.search(r'(\d+\.?\d*)', power_text)
            if match:
                power = float(match.group(1))
                self.root.after(0, self.update_display, power, datetime.now().strftime("%H:%M:%S"), True)
            else:
                self.root.after(0, self.update_display, "格式错误", "无法解析", False)
        except (ValueError, TypeError):
            self.root.after(0, self.update_display, "数据异常", "非数字", False)

    def update_display(self, power, time_str, is_today):
        if not self.root: return
        try:
            power_val = float(power)
            self.power_label.config(text=f"{power_val:.1f}")
            
            if power_val < 20: color = self.colors['low']
            elif power_val < 50: color = self.colors['medium']
            else: color = self.colors['high']
            
            self.power_label.config(fg=color)
            
        except (ValueError, TypeError):
            self.power_label.config(text=str(power), fg=self.colors['fg'])
        
        self.time_label.config(text=f"更新于: {time_str}" if ":" in str(time_str) else str(time_str))

    def animate_in(self):
        self.root.attributes('-alpha', 0.0)
        self.root.deiconify()
        for i in range(10):
            alpha = 0.1 * (i + 1)
            self.root.after(i*20, lambda a=alpha: self.root.attributes('-alpha', a))

    def setup_tray_icon(self):
        def create_image(width, height, color):
            return Image.new('RGB', (width, height), color)
        
        def on_tray_click(icon, item):
            action = {
                "显示/隐藏": self.toggle_visibility,
                "切换宿舍": self.switch_dormitory,
                "前往充值": lambda: open_recharge_page(self.dorm_id, self.dorm_type),
                "查看电量变化(主程序)": open_main_app,
                "退出": self.quit_application
            }.get(str(item))
            if action: self.root.after(0, action)

        menu = (
            pystray.MenuItem(lambda text: "隐藏" if self.is_visible else "显示", on_tray_click),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("切换宿舍", on_tray_click),
            pystray.MenuItem("前往充值", on_tray_click),
            pystray.MenuItem("查看电量变化(主程序)", on_tray_click),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", on_tray_click)
        )
        image = create_image(64, 64, self.colors.get('high', '#4a86e8'))
        self.tray_icon = pystray.Icon("电量监控", image, "电量监控", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _check_events(self):
        if self.root:
            self.root.after(100, self._check_events)
    
    def quit_application(self):
        if self.tray_icon: self.tray_icon.stop()
        if self.root:
            self.root.quit()
            self.root.destroy()
            self.root = None

if __name__ == "__main__":
    if len(sys.argv) >= 4:
        dorm_id, dorm_type, dorm_name = sys.argv[1], sys.argv[2], sys.argv[3]
        try:
            app = PowerWidget(dorm_id, dorm_type, dorm_name)
            app.root.mainloop()
        except tk.TclError as e:
            print(f"Tkinter TclError (expected on exit): {e}")
        except Exception as e:
            import traceback
            with open("widget_error.log", "a", encoding='utf-8') as f:
                f.write(f"{datetime.now()}:\n{traceback.format_exc()}\n")
    else:
        print("Usage: python widget.py <dorm_id> <dorm_type> <dorm_name>")