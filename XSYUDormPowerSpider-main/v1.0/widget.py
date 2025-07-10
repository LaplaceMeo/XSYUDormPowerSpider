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
from PIL import Image, ImageDraw

class PowerWidget:
    def __init__(self, root):
        self.root = root
        self.root.overrideredirect(True)  # 无边框窗口
        self.root.attributes('-topmost', True)  # 窗口置顶
        
        # 初始化数据库管理器
        self.db_manager = DatabaseManager()

        # 加载配置文件中的宿舍信息
        self.dorm_id, self.dorm_name, self.dorm_type = self.load_config()
        if not self.dorm_id:
            messagebox.showerror("错误", "未找到已选择的宿舍信息")
            self.root.destroy()
            return

        # 根据不同平台设置透明度
        self.setup_transparency()

        # 设置窗口大小和位置到右下角
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        widget_width = 180
        widget_height = 120
        x_position = screen_width - widget_width - 20  # 距离右边20像素
        y_position = screen_height - widget_height - 40  # 距离底部40像素
        self.root.geometry(f"{widget_width}x{widget_height}+{x_position}+{y_position}")
        
        # 创建UI元素
        self.create_ui_elements()

        # 记录鼠标位置用于拖动
        self.x = 0
        self.y = 0

        # 设置Matplotlib中文字体
        self.setup_matplotlib_fonts()

        # 开始更新电量
        self.update_power()

        # 绑定事件
        self.bind_events()

        # 添加初始动画
        self.animate_in()
        
        # 系统托盘相关变量
        self.tray_icon = None
        self.is_visible = True
        
        # 用于线程间通信的变量
        self._pending_visibility = None
        
        # 启动时创建托盘图标
        self.setup_tray_icon()
        
        # 启动事件处理循环
        self._check_events()

    def load_config(self):
        """加载配置文件中的宿舍信息"""
        try:
            with open('selected_dorm.cfg', 'r') as f:
                content = f.read().strip()
                dorm_id, dorm_name, dorm_type = content.split('|')
                return dorm_id, dorm_name, dorm_type
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            return None, None, None

    def setup_transparency(self):
        """根据不同平台设置窗口透明度"""
        current_platform = platform.system()
        
        try:
            if current_platform == "Windows":
                # Windows系统支持transparentcolor
                self.root.attributes('-transparentcolor', '#f0f0f0')
            elif current_platform == "Linux":
                # Linux系统使用rgba
                self.root.attributes('-type', 'splash')
            elif current_platform == "Darwin":  # macOS
                # macOS使用特殊的透明度设置
                self.root.configure(bg='systemTransparent')
                self.root.attributes('-alpha', 0.9)  # 半透明
        except Exception as e:
            print(f"设置透明度失败: {e}")
            # 设置一个备用背景色
            self.root.configure(bg="#f0f0f0")

    def setup_matplotlib_fonts(self):
        """设置Matplotlib支持中文显示的字体"""
        try:
            # 尝试几种常见的中文字体
            plt.rcParams["font.family"] = ["SimHei", "WenQuanYi Micro Hei", "Heiti TC", "Microsoft YaHei"]
            # 禁用字体查找警告
            plt.rcParams.update({'font.size': 10})
        except Exception as e:
            print(f"设置中文字体失败: {e}")
            # 如果设置字体失败，使用默认字体
            plt.rcParams["font.family"] = ["sans-serif"]
            # 添加Unicode支持
            plt.rcParams["axes.unicode_minus"] = False

    def create_ui_elements(self):
        """创建所有UI元素"""
        # 创建Canvas作为背景
        self.canvas = tk.Canvas(
            self.root, 
            width=180, 
            height=120, 
            bg="#f0f0f0", 
            highlightthickness=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # 创建圆角背景
        self.create_rounded_background()
        
        # 添加电量图标
        self.create_power_icon()
        
        # 宿舍名称标签
        self.name_label = tk.Label(
            self.canvas, 
            text=self.dorm_name, 
            bg="white", 
            font=("微软雅黑", 10, "bold"),
            fg="#555555"
        )
        self.name_label_window = self.canvas.create_window(
            90, 20, 
            window=self.name_label
        )

        # 电量显示标签
        self.power_label = tk.Label(
            self.canvas, 
            text="加载中...", 
            bg="white", 
            font=("微软雅黑", 28, "bold"),
            fg="#333333"
        )
        self.power_label_window = self.canvas.create_window(
            90, 60, 
            window=self.power_label
        )

        # 更新时间标签
        self.time_label = tk.Label(
            self.canvas, 
            text="", 
            bg="white", 
            font=("微软雅黑", 8),
            fg="#888888"
        )
        self.time_label_window = self.canvas.create_window(
            90, 95, 
            window=self.time_label
        )

    def create_rounded_background(self):
        """创建圆角背景"""
        radius = 15
        points = [
            radius, 5, 175 - radius, 5, 175 - radius, 5, 175, 5, 175, 5 + radius,
            175, 5 + radius, 175, 115 - radius, 175, 115 - radius, 175, 115, 175 - radius, 115,
            175 - radius, 115, radius, 115, radius, 115, 5, 115, 5, 115 - radius,
            5, 115 - radius, 5, 5 + radius, 5, 5 + radius, 5, 5, radius, 5
        ]
        
        # 创建主背景
        self.rounded_rect = self.canvas.create_polygon(
            points, 
            fill="white", 
            outline="#dddddd", 
            width=1
        )
        
        # 添加阴影效果
        shadow_points = [
            radius+2, 7, 175 - radius+2, 7, 175 - radius+2, 7, 177, 7, 177, 5 + radius+2,
            177, 5 + radius+2, 177, 115 - radius+2, 177, 115 - radius+2, 177, 117, 175 - radius+2, 117,
            175 - radius+2, 117, radius+2, 117, radius+2, 117, 7, 117, 7, 115 - radius+2,
            7, 115 - radius+2, 7, 5 + radius+2, 7, 5 + radius+2, 7, 7, radius+2, 7
        ]
        
        self.shadow = self.canvas.create_polygon(
            shadow_points, 
            fill="#000000", 
            outline="#000000", 
            width=0,
            state="hidden"
        )

    def create_power_icon(self):
        """创建电量图标"""
        # 图标坐标
        icon_x = 40
        icon_y = 60
        icon_size = 15
        
        points = [
            icon_x, icon_y - icon_size,
            icon_x + icon_size/2, icon_y,
            icon_x, icon_y + icon_size,
            icon_x - icon_size/2, icon_y
        ]
        
        self.power_icon = self.canvas.create_polygon(
            points, 
            fill="#4a86e8", 
            outline="#3a76d8", 
            width=1
        )

    def bind_events(self):
        """绑定事件处理"""
        # 拖动窗口 - 绑定到整个窗口
        self.root.bind("<Button-1>", self.start_drag)
        self.root.bind("<B1-Motion>", self.on_drag)
        
        # 右键菜单 - 绑定到Canvas
        self.canvas.bind("<Button-3>", self.show_menu)
        
        # 悬停效果
        self.canvas.bind("<Enter>", self.on_enter)
        self.canvas.bind("<Leave>", self.on_leave)
        
        # 双击隐藏窗口
        self.canvas.bind("<Double-1>", self.toggle_visibility)

    def start_drag(self, event):
        """开始拖动窗口"""
        self.x = event.x
        self.y = event.y

    def on_drag(self, event):
        """拖动窗口过程"""
        # 获取当前窗口位置
        x, y = self.root.winfo_x(), self.root.winfo_y()
        
        # 计算新位置
        new_x = x + event.x - self.x
        new_y = y + event.y - self.y
        
        # 设置新位置
        self.root.geometry(f"+{new_x}+{new_y}")

    def on_enter(self, event):
        """鼠标进入时显示阴影"""
        self.canvas.itemconfig(self.shadow, state="normal")
        self.canvas.lower(self.shadow)  # 将阴影置于底层

    def on_leave(self, event):
        """鼠标离开时隐藏阴影"""
        self.canvas.itemconfig(self.shadow, state="hidden")

    def show_menu(self, event):
        """显示右键菜单"""
        menu = Menu(self.root, tearoff=0)
        menu.add_command(label="显示/隐藏", command=self.toggle_visibility)
        menu.add_command(label="切换宿舍", command=self.switch_dormitory)
        menu.add_command(label="前往充值", command=self.go_to_recharge)
        menu.add_command(label="查看电量变化", command=self.view_power_history)
        menu.add_separator()
        menu.add_command(label="退出", command=self.quit_application)
        menu.post(event.x_root, event.y_root)

    def toggle_visibility(self, event=None):
        """切换窗口可见性"""
        if self.is_visible:
            self.hide_window()
        else:
            self.show_window()

    def hide_window(self):
        """隐藏窗口"""
        self.root.withdraw()
        self.is_visible = False
        # 更新托盘图标状态
        if self.tray_icon:
            self.tray_icon.update_menu()

    def show_window(self):
        """显示窗口"""
        # 确保窗口在所有其他窗口前面
        self.root.deiconify()
        self.root.attributes('-topmost', True)
        self.root.attributes('-topmost', False)  # 重置，否则会一直置顶
        self.is_visible = True
        # 更新托盘图标状态
        if self.tray_icon:
            self.tray_icon.update_menu()

    def switch_dormitory(self):
        """切换宿舍（关闭小摆件，打开主程序）"""
        self.quit_application()
        open_main_app()

    def go_to_recharge(self):
        """前往充值页面"""
        open_recharge_page(self.dorm_id, self.dorm_type)

    def view_power_history(self):
        """在新线程中获取并显示电量历史图表"""
        threading.Thread(target=self.show_power_chart, daemon=True).start()

    def show_power_chart(self):
        """获取数据并创建电量历史图表"""
        history = self.db_manager.get_records_by_dorm_id(self.dorm_id, limit=30)
        
        if not history:
            messagebox.showinfo("无记录", "未找到该宿舍的用电历史记录。")
            return

        # 创建图表窗口
        chart_window = tk.Toplevel(self.root)
        chart_window.title(f"{self.dorm_name} 电量变化")
        chart_window.geometry("600x400")
        chart_window.configure(bg="white")

        # 准备数据
        powers = [record[0] for record in reversed(history)]
        times = [record[1].split()[1][:5] for record in reversed(history)]

        # 创建图表
        plt.switch_backend('TkAgg')  # 确保使用Tkinter后端
        fig, ax = plt.subplots(figsize=(6, 4), dpi=100)
        
        # 设置图表样式
        ax.set_facecolor('#f9f9f9')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        
        # 绘制电量曲线
        line, = ax.plot(times, powers, 'o-', color='#4a86e8', linewidth=2.5)
        
        # 设置标题和标签
        ax.set_title(f"{self.dorm_name} 电量变化趋势", fontsize=14, pad=10)
        ax.set_xlabel("时间", fontsize=12, labelpad=5)
        ax.set_ylabel("电量 (度)", fontsize=12, labelpad=5)
        
        # 添加网格
        ax.grid(True, linestyle='--', alpha=0.7, color='#dddddd')
        
        # 在图表上显示数值
        for x, y in zip(times, powers):
            ax.annotate(f'{y}', (x, y), textcoords="offset points", 
                        xytext=(0,10), ha='center', fontsize=10)

        # 将图表嵌入Tkinter窗口
        canvas = FigureCanvasTkAgg(fig, master=chart_window)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def update_power(self):
        threading.Thread(target=self.fetch_power, daemon=True).start()
        # 每30分钟更新一次
        self.root.after(1800000, self.update_power)

    def fetch_power(self):
        """获取最新电量数据"""
        latest_record = self.db_manager.get_records_by_dorm_id(self.dorm_id, limit=1)
        
        if latest_record:
            power, query_time_str = latest_record[0][1], latest_record[0][0]
            query_time = datetime.strptime(query_time_str, '%Y-%m-%d %H:%M:%S.%f')
            is_today = query_time.date() == datetime.now().date()
            self.root.after(0, self.animate_power_change, power, query_time.strftime("%H:%M"), is_today)
        else:
            self.root.after(0, self.update_display, "N/A", "无记录", False)
            
    def animate_power_change(self, target_power, time_str, is_today):
        """电量变化数字动画"""
        try:
            current_text = self.power_label.cget("text")
            current_power = float(current_text.split()[0]) if current_text != "加载中..." and current_text != "暂无数据" and current_text != "获取失败" else target_power
            
            steps = 20
            delta = (target_power - current_power) / steps
            
            def update_step(step):
                if step <= steps:
                    current = current_power + delta * step
                    self.power_label.config(text=f"{current:.1f} 度")
                    self.root.after(20, update_step, step + 1)
                else:
                    self.power_label.config(text=f"{target_power} 度")
                    self.update_display(target_power, time_str, is_today)
            
            update_step(1)
        except Exception as e:
            print(f"电量动画失败: {e}")
            self.update_display(target_power, time_str, is_today)

    def update_display(self, power, time_str, is_today):
        """更新显示内容"""
        # 根据电量设置颜色
        if power < 10:
            self.power_label.config(fg="red")
            # 低电量时图标变红
            self.canvas.itemconfig(self.power_icon, fill="#e64942", outline="#d63932")
        elif power < 30:
            self.power_label.config(fg="orange")
            # 中等电量时图标变黄
            self.canvas.itemconfig(self.power_icon, fill="#f6b26b", outline="#e6a25b")
        else:
            self.power_label.config(fg="#333333")
            # 高电量时图标变蓝
            self.canvas.itemconfig(self.power_icon, fill="#4a86e8", outline="#3a76d8")
            
        # 更新时间标签
        time_text = f"更新于: {time_str.split()[1][:5]}"
        if not is_today:
            time_text += " (非今日数据)"
            
        self.time_label.config(text=time_text)

    def animate_in(self):
        """初始动画效果"""
        # 淡入效果
        self.root.attributes('-alpha', 0.0)
        for i in range(10):
            alpha = 0.1 * (i + 1)
            self.root.after(i * 50, lambda a=alpha: self.root.attributes('-alpha', a))

    def setup_tray_icon(self):
        """设置系统托盘图标"""
        def create_image(width, height, color1, color2, text="?"):
            """创建托盘图标图像"""
            image = Image.new('RGBA', (width, height), color1)
            dc = ImageDraw.Draw(image)
            dc.rectangle((width // 2, 0, width, height // 2), fill=color2)
            dc.rectangle((0, height // 2, width // 2, height), fill=color2)
            dc.text((width // 2 - 4, height // 2 - 5), text, fill="white")
            return image
        
        def on_activate(icon, item):
            """托盘图标点击事件"""
            if str(item) == "显示/隐藏":
                # 使用线程安全的方式请求显示/隐藏
                self._pending_visibility = not self.is_visible
                self.root.after(0, self._process_pending_events)
            elif str(item) == "切换宿舍":
                self.root.after(0, self.switch_dormitory)
            elif str(item) == "前往充值":
                self.root.after(0, self.go_to_recharge)
            elif str(item) == "查看电量变化":
                self.root.after(0, self.view_power_history)
            elif str(item) == "退出":
                self.root.after(0, self.quit_application)
        
        # 创建托盘菜单
        menu = (
            pystray.MenuItem(lambda icon: "隐藏" if self.is_visible else "显示", on_activate),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("切换宿舍", on_activate),
            pystray.MenuItem("前往充值", on_activate),
            pystray.MenuItem("查看电量变化", on_activate),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", on_activate)
        )
        
        # 创建初始图标
        image = create_image(64, 64, "#4a86e8", "#3a76d8")
        
        # 创建托盘图标
        self.tray_icon = pystray.Icon(
            "电量监控",
            image,
            "电量监控",
            menu
        )
        
        # 在后台线程中运行托盘图标
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def update_tray_icon(self, power):
        """更新托盘图标"""
        if not self.tray_icon:
            return
            
        def create_image(width, height, color1, color2, text):
            """创建托盘图标图像"""
            image = Image.new('RGBA', (width, height), color1)
            dc = ImageDraw.Draw(image)
            dc.rectangle((width // 2, 0, width, height // 2), fill=color2)
            dc.rectangle((0, height // 2, width // 2, height), fill=color2)
            dc.text((width // 2 - 4, height // 2 - 5), text, fill="white")
            return image
        
        # 根据电量设置图标颜色
        if power < 10:
            color1 = "#e64942"  # 红色
            color2 = "#d63932"
        elif power < 30:
            color1 = "#f6b26b"  # 橙色
            color2 = "#e6a25b"
        else:
            color1 = "#4a86e8"  # 蓝色
            color2 = "#3a76d8"
        
        # 创建新图标
        power_text = f"{power:.0f}"
        new_image = create_image(64, 64, color1, color2, power_text)
        
        # 更新托盘图标
        self.tray_icon.icon = new_image
        self.tray_icon.title = f"{self.dorm_name}: {power:.1f} 度"

    def _check_events(self):
        """检查并处理待处理的事件"""
        self._process_pending_events()
        # 每100毫秒检查一次
        self.root.after(100, self._check_events)

    def _process_pending_events(self):
        """处理待处理的事件"""
        if self._pending_visibility is not None:
            if self._pending_visibility:
                self.show_window()
            else:
                self.hide_window()
            self._pending_visibility = None

    def quit_application(self):
        """安全退出应用程序"""
        # 设置标志以停止托盘图标线程
        if self.tray_icon:
            self.tray_icon.stop()
        self.db_manager.close()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = PowerWidget(root)
    root.mainloop()