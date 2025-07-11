import tkinter as tk
from tkinter import Menu, messagebox
import threading
import time
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import subprocess
import sys
from database import DatabaseManager
from utils import open_main_app, open_recharge_page, predict_remaining_days # 导入预测函数
import platform
from datetime import datetime
import pystray
from PIL import Image, ImageDraw, ImageFont, ImageTk
import re
import os # 新增os模块
import shutil # 新增shutil模块

# 获取当前文件所在的目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

from config import ConfigManager
from scraper import Scraper

def create_placeholder_image(size, text, color, file_path):
    """
    创建一个带文本的占位符图片并保存。
    """
    if os.path.exists(file_path):
        return
    img = Image.new('RGBA', (size, size), (255, 255, 255, 0)) # 透明背景
    draw = ImageDraw.Draw(img)
    
    # 简单的背景形状
    draw.ellipse((10, 10, size-10, size-10), fill=color)
    
    # 添加文本
    try:
        font = ImageFont.truetype("msyh.ttc", size // 4)
    except IOError:
        font = ImageFont.load_default()
    
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    draw.text(((size - text_width) / 2, (size - text_height) / 2), text, fill="white", font=font)
    
    img.save(file_path)

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

        # 检查并创建图片资源
        self.prepare_pet_images()

        # Correctly read the 'Widget' section for the style
        self.style_name = self.config_manager.get_setting('Widget', 'style', '默认')
        
        self.setup_transparency()

        # 初始尺寸和位置
        self.widget_width = 180
        self.widget_height = 120
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x_position = screen_width - self.widget_width - 20
        y_position = screen_height - self.widget_height - 40
        self.root.geometry(f"{self.widget_width}x{self.widget_height}+{x_position}+{y_position}")

        self.setup_colors()
        self.create_ui_elements()

        self.x = 0
        self.y = 0

        # 新增：用于调整窗口大小的变量
        self.resizing = False
        self.resize_edge = None
        # 新增：用于存放2D数字人图片的变量
        self.pet_image = None
        self.pet_label = None
        # 新增：用于缓存加载的图片，避免重复读取
        self.pet_images_cache = {}


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
        elif self.style_name == '数字宠物':
             self.colors = {
                'bg': '#E0F7FA', 'fg': '#004D40', 'low': '#D9534F',
                'medium': '#F0AD4E', 'high': '#5CB85C', 'outline': '#B2DFDB', 'icon': '#00796B'
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
        self.canvas = tk.Canvas(self.root, width=self.widget_width, height=self.widget_height, bg=self.root.cget('bg'), highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.name_label = tk.Label(self.canvas, text=self.dorm_name, bg=self.colors['bg'], font=("微软雅黑", 10, "bold"), fg=self.colors['fg'])
        self.power_label = tk.Label(self.canvas, text="加载中...", bg=self.colors['bg'], font=("微软雅黑", 28, "bold"), fg=self.colors['fg'])
        self.time_label = tk.Label(self.canvas, text="", bg=self.colors['bg'], font=("微软雅黑", 8), fg=self.colors['fg'])
        # 新增：用于显示预测结果的标签
        self.prediction_label = tk.Label(self.canvas, text="", bg=self.colors['bg'], font=("微软雅黑", 8), fg=self.colors['fg'])

        # 如果是数字宠物风格，则创建用于显示2D形象的Label
        if self.style_name == '数字宠物':
            self.pet_label = tk.Label(self.canvas, bg=self.colors['bg'])
            # 初始加载一个默认或“加载中”的形象
            self.update_pet_image(200) # 假设初始电量很高

        self.redraw_canvas() # 初始绘制

    def redraw_canvas(self):
        """重新绘制所有canvas元素，以适应窗口大小变化"""
        self.canvas.delete("all")
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        
        # 绘制背景
        self.create_rounded_background(width, height)

        # 绘制附加装饰
        if self.style_name == '猫娘':
            self.create_cat_ears(width, height)
        
        # 放置文本标签
        name_y = height * 0.18
        power_y = height * 0.5
        time_y = height * 0.82
        prediction_y = height * 0.95 # 预测标签的位置
        
        self.canvas.create_window(width/2, name_y, window=self.name_label)
        self.canvas.create_window(width/2, power_y, window=self.power_label)
        self.canvas.create_window(width/2, time_y, window=self.time_label)
        self.canvas.create_window(width/2, prediction_y, window=self.prediction_label) # 添加到canvas

        # 动态调整字体大小
        power_font_size = max(12, min(28, int(height / 4)))
        self.power_label.config(font=("微软雅黑", power_font_size, "bold"))
        self.name_label.config(font=("微软雅黑", max(8, int(power_font_size / 2.8)), "bold"))
        base_font_size = max(6, int(power_font_size / 3.5))
        self.time_label.config(font=("微软雅黑", base_font_size))
        self.prediction_label.config(font=("微软雅黑", base_font_size))


        # 放置数字宠物
        if self.style_name == '数字宠物' and self.pet_label:
            pet_size = int(min(width, height) * 0.4)
            self.pet_label.place(x=width*0.05, y=height*0.3, width=pet_size, height=pet_size)

    def create_rounded_background(self, width, height):
        """根据当前宽高绘制圆角背景"""
        radius = 20
        # 使用多边形创建更平滑的圆角矩形
        points = [
            (radius, 0), (width - radius, 0),
            (width, radius), (width, height - radius),
            (width - radius, height), (radius, height),
            (0, height - radius), (0, radius)
        ]
        self.canvas.create_polygon(points, fill=self.colors['bg'], outline=self.colors['outline'], width=1)


    def create_cat_ears(self, width, height):
        # 猫耳朵的位置和大小应相对于当前窗口尺寸
        ear_width = width * 0.15
        ear_height = height * 0.2
        # 左耳
        self.canvas.create_polygon(width*0.1, height*0.15, width*0.1+ear_width, height*0.05, width*0.1+ear_width, height*0.15+ear_height, 
                                   fill=self.colors['bg'], outline=self.colors['outline'], width=1)
        # 右耳
        self.canvas.create_polygon(width*0.9, height*0.15, width*0.9-ear_width, height*0.05, width*0.9-ear_width, height*0.15+ear_height,
                                   fill=self.colors['bg'], outline=self.colors['outline'], width=1)

    def create_power_icon(self):
        # 此函数暂时不再直接调用，因为图标可以集成到数字人或背景中
        pass
    
    def bind_events(self):
        """为窗口和画布绑定事件"""
        # 拖动和右键菜单
        self.root.bind("<Button-1>", self.start_drag)
        self.root.bind("<B1-Motion>", self.on_drag)
        self.root.bind("<ButtonRelease-1>", self.stop_resize) # 新增：释放鼠标时完成调整
        self.root.bind("<Button-3>", self.show_menu)
        self.root.bind("<Double-1>", self.toggle_visibility)

        # 进入和离开窗口事件，用于改变光标
        self.root.bind("<Enter>", self.on_enter)
        self.root.bind("<Leave>", self.on_leave)
        # 鼠标移动事件，用于检测是否在边缘
        self.root.bind("<Motion>", self.check_resize_cursor)


    def start_drag(self, event):
        """
        记录鼠标按下的初始位置。
        如果鼠标在边缘，则启动调整大小模式。
        """
        if self.resize_edge:
            self.resizing = True
        else:
            self.x, self.y = event.x, event.y

    def on_drag(self, event):
        """
        根据鼠标移动来拖动窗口或调整窗口大小。
        """
        if self.resizing:
            self.resize_window(event)
        else:
            new_x = self.root.winfo_x() + event.x - self.x
            new_y = self.root.winfo_y() + event.y - self.y
            self.root.geometry(f"+{new_x}+{new_y}")

    def stop_resize(self, event):
        """鼠标释放后停止调整大小并重绘界面"""
        if self.resizing:
            self.resizing = False
            self.redraw_canvas()

    def check_resize_cursor(self, event):
        """检查鼠标是否在窗口边缘，并相应地改变光标形状。"""
        x, y = event.x, event.y
        width, height = self.root.winfo_width(), self.root.winfo_height()
        edge_margin = 5  # 边缘检测的容差范围

        if x < edge_margin and y < edge_margin:
            self.resize_edge = "top-left"
            self.root.config(cursor="size_nw_se")
        elif x > width - edge_margin and y > height - edge_margin:
            self.resize_edge = "bottom-right"
            self.root.config(cursor="size_nw_se")
        elif x > width - edge_margin and y < edge_margin:
            self.resize_edge = "top-right"
            self.root.config(cursor="size_ne_sw")
        elif x < edge_margin and y > height - edge_margin:
            self.resize_edge = "bottom-left"
            self.root.config(cursor="size_ne_sw")
        elif x < edge_margin:
            self.resize_edge = "left"
            self.root.config(cursor="sb_h_double_arrow")
        elif x > width - edge_margin:
            self.resize_edge = "right"
            self.root.config(cursor="sb_h_double_arrow")
        elif y < edge_margin:
            self.resize_edge = "top"
            self.root.config(cursor="sb_v_double_arrow")
        elif y > height - edge_margin:
            self.resize_edge = "bottom"
            self.root.config(cursor="sb_v_double_arrow")
        else:
            self.resize_edge = None
            self.root.config(cursor="")

    def resize_window(self, event):
        """根据拖动方向调整窗口大小和位置"""
        width, height = self.root.winfo_width(), self.root.winfo_height()
        x, y = self.root.winfo_x(), self.root.winfo_y()

        # 根据鼠标相对于屏幕的位置来计算新的尺寸和位置
        new_width, new_height = width, height
        new_x, new_y = x, y

        if "right" in self.resize_edge:
            new_width = event.x_root - x
        if "left" in self.resize_edge:
            new_width = width - (event.x_root - x)
            new_x = event.x_root
        
        if "bottom" in self.resize_edge:
            new_height = event.y_root - y
        if "top" in self.resize_edge:
            new_height = height - (event.y_root - y)
            new_y = event.y_root

        # 设置最小尺寸防止窗口过小
        new_width = max(new_width, 100)
        new_height = max(new_height, 80)
        
        self.root.geometry(f"{new_width}x{new_height}+{new_x}+{new_y}")
        self.redraw_canvas() # 在调整大小时实时重绘

    def on_enter(self, event):
        """鼠标进入窗口时触发"""
        self.check_resize_cursor(event)

    def on_leave(self, event):
        """鼠标离开窗口时，重置光标"""
        self.root.config(cursor="")
        self.resizing = False # 离开窗口时停止调整大小
    
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
        prediction_status, prediction_result = predict_remaining_days(self.dorm_id) # 获取预测结果

        if not self.root: return
        
        if error_message:
            return self.root.after(0, self.update_display, "获取失败", "请检查网络", "无法预测", False)
        
        try:
            match = re.search(r'(\d+\.?\d*)', power_text)
            if match:
                power = float(match.group(1))
                self.root.after(0, self.update_display, power, datetime.now().strftime("%H:%M:%S"), (prediction_status, prediction_result), True)
                # 更新数字宠物形象
                if self.style_name == '数字宠物':
                    self.root.after(0, self.update_pet_image, power)
            else:
                self.root.after(0, self.update_display, "格式错误", "无法解析", (prediction_status, prediction_result), False)
        except (ValueError, TypeError):
            self.root.after(0, self.update_display, "数据异常", "非数字", (prediction_status, prediction_result), False)

    def update_display(self, power, time_str, prediction_data, is_today):
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

        # 更新预测标签
        pred_status, pred_result = prediction_data
        if pred_status == 'predict':
            pred_text = f"预计可用: {pred_result} 天"
        elif pred_status == 'sufficient':
            pred_text = "电量充足"
        else:
            pred_text = "暂无预测"
        self.prediction_label.config(text=pred_text)

        self.redraw_canvas() # 更新显示后也重绘一下，确保所有元素位置正确

    def animate_in(self):
        self.root.attributes('-alpha', 0.0)
        self.root.deiconify()
        for i in range(10):
            alpha = 0.1 * (i + 1)
            self.root.after(i*20, lambda a=alpha: self.root.attributes('-alpha', a))

    def prepare_pet_images(self):
        """检查并准备数字宠物所需的图片资源"""
        # 使用基于当前文件位置的相对路径，使程序更健壮
        img_dir = os.path.join(BASE_DIR, '..', 'img') # 向上回退一级到v1.0的父目录，再进入img
        if not os.path.exists(img_dir):
            os.makedirs(img_dir)
            
        # 定义图片路径
        self.pet_image_paths = {
            'high': os.path.join(img_dir, 'pet_high.png'),
            'medium': os.path.join(img_dir, 'pet_medium.png'),
            'low': os.path.join(img_dir, 'pet_low.png')
        }

        # 复制现有图片
        source_high_img = os.path.join(img_dir, '电量充足.png')
        if os.path.exists(source_high_img):
            shutil.copy2(source_high_img, self.pet_image_paths['high'])
        else:
            # 如果源文件也不存在，则也为high创建一个占位符
            create_placeholder_image(128, "电量高", "#5CB85C", self.pet_image_paths['high'])

        # 创建中等和低电量占位图
        create_placeholder_image(128, "电量中", "#F0AD4E", self.pet_image_paths['medium'])
        create_placeholder_image(128, "电量低", "#D9534F", self.pet_image_paths['low'])


    def update_pet_image(self, power_level):
        """根据电量更新2D数字人宠物的图片"""
        if self.style_name != '数字宠物':
            return

        if power_level < 20:
            state = 'low'
        elif power_level < 50:
            state = 'medium'
        else:
            state = 'high'
            
        image_path = self.pet_image_paths.get(state)

        if not image_path or not os.path.exists(image_path):
            return # 如果图片路径不存在，则不执行任何操作

        try:
            # 动态调整图片大小以适应标签
            width = self.pet_label.winfo_width()
            height = self.pet_label.winfo_height()
            
            # 确保尺寸大于0
            if width <= 1 or height <= 1:
                # 如果label尺寸无效，可能是窗口还未完全绘制，稍后重试
                self.root.after(50, lambda: self.update_pet_image(power_level))
                return

            # 从缓存加载图片以提高性能
            if state in self.pet_images_cache and self.pet_images_cache[state]['size'] == (width, height):
                 self.pet_image = self.pet_images_cache[state]['image']
            else:
                original_image = Image.open(image_path).convert("RGBA")
                resized_image = original_image.resize((width, height), Image.LANCZOS)
                self.pet_image = ImageTk.PhotoImage(resized_image)
                # 更新缓存
                self.pet_images_cache[state] = {'image': self.pet_image, 'size': (width, height)}

            if self.pet_label:
                self.pet_label.config(image=self.pet_image)
        except Exception as e:
            print(f"Error updating pet image: {e}")


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