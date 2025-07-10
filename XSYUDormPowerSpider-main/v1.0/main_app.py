# 主程序（原有的电量查询系统）
import requests
from bs4 import BeautifulSoup
import re
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import webbrowser
import time
from collections import defaultdict
import sqlite3
import csv
import subprocess
import sys
from datetime import datetime  # 显式导入datetime类
import os
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from thefuzz import process
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates

from database import DatabaseManager
from scraper import Scraper
from config import ConfigManager

class DormitoryPowerChecker:
    def __init__(self, root):
        # 初始化模块
        self.config_manager = ConfigManager()
        self.db_manager = DatabaseManager()
        self.scraper = Scraper()

        self.root = root
        
        # 应用保存的主题和窗口设置
        initial_theme = self.config_manager.get_setting('Theme', 'current_theme', 'litera')
        self.style = ttk.Style(theme=initial_theme)
        initial_geometry = self.config_manager.get_setting('Window', 'geometry', '900x800')
        self.root.geometry(initial_geometry)
        
        self.root.title("宿舍电量查询与充值系统")

        # 宿舍数据存储
        self.dormitories = []
        self.id_mapping = {}

        # 加载宿舍数据
        self.load_dormitory_data()

        # 创建界面
        self.create_widgets()
        self.create_menu()

        # 绑定窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def init_database(self):
        """初始化SQLite数据库和记录表"""
        self.conn = sqlite3.connect('electricity_data.db')
        self.cursor = self.conn.cursor()
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS electricity_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dorm_id TEXT,
                dorm_name TEXT,
                query_time DATETIME,
                power FLOAT
            )
        ''')
        self.conn.commit()

    def load_dormitory_data(self):
        """从CSV文件中加载宿舍数据"""
        try:
            # 检查是否是打包后的可执行文件
            if getattr(sys, 'frozen', False):
                # 如果是打包后的可执行文件，获取可执行文件所在目录
                base_path = sys._MEIPASS
            else:
                # 如果是开发环境，获取当前脚本所在目录
                base_path = os.path.dirname(os.path.abspath(__file__))

            file_path = os.path.join(base_path, 'dorm_rooms_2025.csv')
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    building = row['building']
                    room_number = row['room_number']
                    dorm_id = row['room_code']
                    dorm_type = row['dorm_type']
                    name = f"{building}-{room_number}"
                    self.dormitories.append({'name': name, 'id': dorm_id, 'type': dorm_type})
                    self.id_mapping[dorm_id] = (name, dorm_type)
        except Exception as e:
            messagebox.showerror("错误", f"无法读取文件: {str(e)}")

    def create_widgets(self):
        """创建界面组件"""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=BOTH, expand=YES)

        title_label = ttk.Label(main_frame, text="宿舍电量查询与充值系统", font=("微软雅黑", 20, "bold"), bootstyle="primary")
        title_label.pack(pady=(0, 20))

        search_frame = ttk.Frame(main_frame)
        search_frame.pack(fill=X, pady=5)

        search_label = ttk.Label(search_frame, text="输入房间号进行搜索:", font=("微软雅黑", 12))
        search_label.pack(side=LEFT, padx=(0, 10))

        self.search_entry = ttk.Entry(search_frame, font=("微软雅黑", 12), width=50)
        self.search_entry.pack(side=LEFT, fill=X, expand=YES)
        self.search_entry.bind("<KeyRelease>", self.on_search)

        result_frame = ttk.LabelFrame(main_frame, text="搜索结果", padding="10", bootstyle="info")
        result_frame.pack(fill=BOTH, expand=YES, pady=10)

        self.scrollbar = ttk.Scrollbar(result_frame, bootstyle="round-primary")
        self.scrollbar.pack(side=RIGHT, fill=Y)

        columns = ("name", "id")
        self.result_tree = ttk.Treeview(
            result_frame,
            columns=columns,
            show="headings",
            yscrollcommand=self.scrollbar.set,
            bootstyle="primary"
        )
        self.result_tree.heading("name", text="宿舍名称")
        self.result_tree.heading("id", text="宿舍ID")
        self.result_tree.column("name", width=400, anchor=W)
        self.result_tree.column("id", width=200, anchor=W)
        self.result_tree.pack(side=LEFT, fill=BOTH, expand=YES)

        self.scrollbar.config(command=self.result_tree.yview)

        self.result_tree.bind("<Double-1>", self.on_result_double_click)

        query_frame = ttk.LabelFrame(main_frame, text="电量查询结果", padding="10", bootstyle="info")
        query_frame.pack(fill=X, pady=10)

        self.query_result = scrolledtext.ScrolledText(query_frame, height=8, font=("微软雅黑", 10), relief="flat")
        self.query_result.pack(fill=X, expand=YES)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=X, pady=10)

        self.query_button = ttk.Button(button_frame, text="查询电量", command=self.query_power, state=DISABLED, bootstyle="success")
        self.query_button.pack(side=LEFT, padx=5, ipady=5)

        self.recharge_button = ttk.Button(button_frame, text="前往充值", command=self.recharge_dormitory, state=DISABLED, bootstyle="info")
        self.recharge_button.pack(side=LEFT, padx=5, ipady=5)
        
        self.create_widget_button = ttk.Button(button_frame, text="创建桌面小摆件", command=self.create_desktop_widget, state=DISABLED, bootstyle="warning")
        self.create_widget_button.pack(side=LEFT, padx=5, ipady=5)

        self.history_button = ttk.Button(button_frame, text="查看历史用电", command=self.show_history_graph, state=DISABLED, bootstyle="secondary")
        self.history_button.pack(side=LEFT, padx=5, ipady=5)

        clear_button = ttk.Button(button_frame, text="清空", command=self.clear_all, bootstyle="danger")
        clear_button.pack(side=RIGHT, padx=5, ipady=5)

    def create_menu(self):
        """创建顶部菜单栏"""
        menu_bar = ttk.Menu(self.root)
        self.root.config(menu=menu_bar)

        theme_menu = ttk.Menu(menu_bar, tearoff=False)
        menu_bar.add_cascade(label="主题", menu=theme_menu)

        # 提供一些美观的主题选项
        themes = ['litera', 'cosmo', 'flatly', 'journal', 'lumen', 'minty', 'pulse', 'sandstone', 'united', 'yeti',
                  'cyborg', 'darkly', 'solar', 'superhero']
        
        for theme_name in themes:
            theme_menu.add_command(label=theme_name, command=lambda t=theme_name: self.change_theme(t))

    def change_theme(self, theme_name):
        """切换并保存主题"""
        self.style.theme_use(theme_name)
        self.config_manager.set_setting('Theme', 'current_theme', theme_name)

    def on_search(self, event=None):
        """处理搜索事件，使用thefuzz进行模糊匹配"""
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)

        search_text = self.search_entry.get().strip()
        if not search_text:
            self.query_button.config(state=DISABLED)
            self.recharge_button.config(state=DISABLED)
            self.create_widget_button.config(state=DISABLED)
            self.history_button.config(state=DISABLED)
            return

        # 使用thefuzz进行模糊搜索
        choices = [d['name'] for d in self.dormitories]
        results = process.extract(search_text, choices, limit=50)

        found_dorms = []
        for name, score in results:
            if score > 70:  # 仅显示相似度高于70的结果
                for dorm in self.dormitories:
                    if dorm['name'] == name:
                        found_dorms.append(dorm)
                        break
        
        for dorm in found_dorms:
            self.result_tree.insert("", tk.END, values=(dorm['name'], dorm['id']))

        button_state = NORMAL if found_dorms else DISABLED
        self.query_button.config(state=button_state)
        self.recharge_button.config(state=button_state)
        self.create_widget_button.config(state=button_state)
        self.history_button.config(state=button_state)

    def on_result_double_click(self, event):
        """处理结果双击事件"""
        item = self.result_tree.selection()
        if item:
            values = self.result_tree.item(item, "values")
            if values:
                self.query_power()

    def query_power(self):
        """查询宿舍电量"""
        item = self.result_tree.selection()
        if not item:
            messagebox.showwarning("警告", "请先从列表中选择一个宿舍")
            return

        values = self.result_tree.item(item, "values")
        if not values:
            return

        dorm_name, dorm_id = values[:2]
        dorm_type = self.id_mapping[dorm_id][1]
        self.query_result.delete(1.0, tk.END)
        self.query_result.insert(tk.END, f"正在查询 {dorm_name} (ID: {dorm_id}) 的电量...\n")
        self.root.update()

        threading.Thread(target=self.query_power_in_thread, args=(dorm_id, dorm_name, dorm_type), daemon=True).start()

    def query_power_in_thread(self, dorm_id, dorm_name, dorm_type):
        """在新线程中查询电量"""
        power_text, error_message = self.scraper.get_power(dorm_id, dorm_type)

        if error_message:
            result = f"查询失败：{error_message}"
        else:
            result = f"{dorm_name} (ID: {dorm_id}) 的剩余电量为: {power_text} 度"
            try:
                power_float = float(power_text)
                self.db_manager.save_record(dorm_id, dorm_name, power_float)
            except (ValueError, TypeError):
                # 如果电量值无法转换，就不保存到数据库
                pass

        self.root.after(0, self.update_query_result, result)

    def update_query_result(self, result):
        """在主线程中更新UI"""
        self.query_result.insert(tk.END, f"{result}\n")
        self.query_result.see(tk.END)

    def recharge_dormitory(self):
        """宿舍充值功能"""
        item = self.result_tree.selection()
        if not item:
            messagebox.showwarning("警告", "请先选择一个宿舍")
            return

        values = self.result_tree.item(item, "values")
        if not values:
            return

        dorm_name, dorm_id = values[:2]
        dorm_type = self.id_mapping[dorm_id][1]

        recharge_url = f"https://hydz.xsyu.edu.cn/wxpay/homeinfo.aspx?xid={dorm_id}&type={dorm_type}&opid=a"

        if messagebox.askyesno("确认充值", f"是否跳转到 {dorm_name} 的充值页面?"):
            webbrowser.open(recharge_url)

    def clear_all(self):
        """清空所有输入和结果"""
        self.search_entry.delete(0, tk.END)
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)
        self.query_result.delete(1.0, tk.END)
        self.query_button.config(state=DISABLED)
        self.recharge_button.config(state=DISABLED)
        self.create_widget_button.config(state=DISABLED)
        self.history_button.config(state=DISABLED)

    def create_desktop_widget(self):
        """创建并启动桌面小摆件"""
        item = self.result_tree.selection()
        if not item:
            messagebox.showwarning("警告", "请先选择一个宿舍")
            return

        values = self.result_tree.item(item, "values")
        if not values:
            return

        dorm_name, dorm_id = values[:2]
        dorm_type = self.id_mapping[dorm_id][1]

        # 保存当前选择的宿舍信息到配置文件
        with open('selected_dorm.cfg', 'w') as f:
            f.write(f"{dorm_id}|{dorm_name}|{dorm_type}")

        # 启动小部件进程
        widget_script = os.path.join(os.path.dirname(__file__), 'widget.py')
        subprocess.Popen([sys.executable, widget_script])
        
        self.on_closing() # 使用on_closing来确保配置被保存

    def show_history_graph(self):
        """显示选中宿舍的用电历史图表"""
        item = self.result_tree.selection()
        if not item:
            messagebox.showwarning("提示", "请先在列表中选择一个宿舍。")
            return
        
        values = self.result_tree.item(item, "values")
        dorm_name, dorm_id = values[:2]

        records = self.db_manager.get_records_by_dorm_id(dorm_id, limit=30)

        if not records:
            messagebox.showinfo("无历史数据", f"未找到宿舍 {dorm_name} 的历史用电数据。")
            return

        # 创建新窗口用于显示图表
        graph_window = tk.Toplevel(self.root)
        graph_window.title(f"{dorm_name} - 用电历史")
        graph_window.geometry("800x600")

        # 数据处理
        dates = [datetime.strptime(rec[0], '%Y-%m-%d %H:%M:%S.%f') for rec in records]
        power_values = [rec[1] for rec in records]

        # 创建图表
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(dates, power_values, marker='o', linestyle='-')
        
        # 美化图表
        ax.set_title(f'{dorm_name} 最近30天用电趋势', fontsize=16)
        ax.set_xlabel('日期', fontsize=12)
        ax.set_ylabel('剩余电量 (度)', fontsize=12)
        ax.grid(True, which='both', linestyle='--', linewidth=0.5)
        
        # 格式化X轴日期显示
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=5)) # 每5天显示一个刻度
        fig.autofmt_xdate() # 自动旋转日期标签

        # 将图表嵌入到Tkinter窗口
        canvas = FigureCanvasTkAgg(fig, master=graph_window)
        canvas.draw()
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

            
    def on_closing(self):
        """处理窗口关闭事件，保存配置并关闭数据库连接"""
        # 保存最后的窗口位置和大小
        self.config_manager.set_setting('Window', 'geometry', self.root.winfo_geometry())
        self.config_manager.save_config()
        
        # db_manager现在是线程安全的，但在主线程退出时最好还是显式关闭一下连接
        self.db_manager.close()
        
        self.root.destroy()

def main():
    try:
        # 主窗口需要用tk.Tk()来创建，以便ttk-bootstrap正确应用样式
        root = tk.Tk()
        app = DormitoryPowerChecker(root)
        root.mainloop()
    except Exception as e:
        import traceback
        with open("error.log", "a") as f:
            f.write(f"{datetime.now()}: {traceback.format_exc()}\n")
        messagebox.showerror("致命错误", f"发生未处理的异常: {e}\n详情请见error.log")

if __name__ == "__main__":
    main()