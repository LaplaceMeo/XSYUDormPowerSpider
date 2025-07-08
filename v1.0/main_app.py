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
class DormitoryPowerChecker:
    def __init__(self, root):
        self.root = root
        self.root.title("宿舍电量查询与充值系统")
        self.root.geometry("850x750")
        self.root.resizable(True, True)

        # 数据库初始化
        self.init_database()

        # 宿舍数据存储
        self.dormitories = []
        self.id_mapping = {}
        self.name_mapping = defaultdict(list)

        # 加载宿舍数据
        self.load_dormitory_data()

        # 创建界面
        self.create_widgets()

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
                    self.dormitories.append((name, dorm_id, dorm_type))
                    self.id_mapping[dorm_id] = (name, dorm_type)
                    for keyword in self.extract_keywords(name):
                        self.name_mapping[keyword].append((name, dorm_id, dorm_type))
        except Exception as e:
            messagebox.showerror("错误", f"无法读取文件: {str(e)}")

    def extract_keywords(self, name):
        """从宿舍名称中提取关键词用于模糊搜索"""
        keywords = []
        keywords.append(name)
        keywords.extend(name.split('-'))
        numbers = re.findall(r'\d+', name)
        keywords.extend(numbers)
        return keywords

    def create_widgets(self):
        """创建界面组件"""
        title_label = tk.Label(self.root, text="宿舍电量查询与充值系统", font=("微软雅黑", 16, "bold"))
        title_label.pack(pady=10)

        search_frame = ttk.LabelFrame(self.root, text="宿舍搜索")
        search_frame.pack(fill=tk.X, padx=20, pady=5)

        search_label = ttk.Label(search_frame, text="输入房间号进行搜索:")
        search_label.pack(side=tk.LEFT)

        self.search_entry = ttk.Entry(search_frame, width=50)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.search_entry.bind("<KeyRelease>", self.on_search)

        search_button = ttk.Button(search_frame, text="搜索", command=self.on_search)
        search_button.pack(side=tk.LEFT, padx=5)

        result_frame = ttk.LabelFrame(self.root, text="搜索结果")
        result_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        self.scrollbar = ttk.Scrollbar(result_frame)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        columns = ("name", "id", "action")
        self.result_tree = ttk.Treeview(
            result_frame,
            columns=columns,
            show="headings",
            yscrollcommand=self.scrollbar.set
        )
        self.result_tree.heading("name", text="宿舍名称")
        self.result_tree.heading("id", text="宿舍ID")
        self.result_tree.heading("action", text="操作")
        self.result_tree.column("name", width=300)
        self.result_tree.column("id", width=150)
        self.result_tree.column("action", width=100)
        self.result_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.scrollbar.config(command=self.result_tree.yview)

        self.result_tree.bind("<Double-1>", self.on_result_double_click)
        self.result_tree.bind("<Button-1>", self.on_tree_click)

        query_frame = ttk.LabelFrame(self.root, text="电量查询结果")
        query_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        self.query_result = scrolledtext.ScrolledText(query_frame, height=10)
        self.query_result.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        recharge_frame = ttk.LabelFrame(self.root, text="宿舍充值")
        recharge_frame.pack(fill=tk.X, padx=20, pady=5)

        self.recharge_info = ttk.Label(recharge_frame, text="请先搜索并选择宿舍", foreground="blue")
        self.recharge_info.pack(side=tk.LEFT, padx=5, pady=5)

        self.recharge_button = ttk.Button(recharge_frame, text="前往充值", command=self.recharge_dormitory, state=tk.DISABLED)
        self.recharge_button.pack(side=tk.RIGHT, padx=5, pady=5)

        # 新增：创建桌面小摆件按钮
        self.create_widget_button = ttk.Button(recharge_frame, text="创建桌面小摆件", command=self.create_desktop_widget)
        self.create_widget_button.pack(side=tk.RIGHT, padx=5, pady=5)

        button_frame = ttk.Frame(self.root)
        button_frame.pack(fill=tk.X, padx=20, pady=10)

        self.query_button = ttk.Button(button_frame, text="查询电量", command=self.query_power, state=tk.DISABLED)
        self.query_button.pack(side=tk.LEFT, padx=5)

        clear_button = ttk.Button(button_frame, text="清空", command=self.clear_all)
        clear_button.pack(side=tk.LEFT, padx=5)

    def on_search(self, event=None):
        """处理搜索事件"""
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)

        search_text = self.search_entry.get().strip().lower()
        if not search_text:
            return

        results = []
        keywords = self.extract_keywords(search_text)
        found_ids = set()

        for keyword in keywords:
            for name, dorm_id, dorm_type in self.name_mapping.get(keyword, []):
                if dorm_id not in found_ids:
                    results.append((name, dorm_id, dorm_type))
                    found_ids.add(dorm_id)

        for name, dorm_id, dorm_type in results:
            self.result_tree.insert("", tk.END, values=(name, dorm_id, "充值"))

        button_state = tk.NORMAL if results else tk.DISABLED
        self.query_button.config(state=button_state)
        self.recharge_button.config(state=button_state)
        self.create_widget_button.config(state=button_state)

    def on_tree_click(self, event):
        """处理Treeview点击事件"""
        item = self.result_tree.identify_row(event.y)
        if not item:
            return

        column = self.result_tree.identify_column(event.x)
        if column == "#3":  # 操作列
            self.recharge_dormitory()

    def on_result_double_click(self, event):
        """处理结果双击事件"""
        item = self.result_tree.selection()
        if item:
            values = self.result_tree.item(item, "values")
            if values:
                self.search_entry.delete(0, tk.END)
                self.search_entry.insert(0, values[0])
                self.query_power()

    def query_power(self):
        """查询宿舍电量"""
        item = self.result_tree.selection()
        if not item:
            messagebox.showwarning("警告", "请先选择一个宿舍")
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
        try:
            url = f"http://hydz.xsyu.edu.cn/wxpay/homeinfo.aspx?xid={dorm_id}&type={dorm_type}&opid=a"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Referer": "https://hydz.xsyu.edu.cn/wxpay/homeinfo.aspx",
            }

            response = requests.get(url, headers=headers, timeout=15)
            response.encoding = 'utf-8'

            soup = BeautifulSoup(response.text, 'html.parser')

            power_span = soup.find('span', id='lblSYDL') or soup.find('span', id='Label1')
            if not power_span:
                result = f"错误：未找到剩余电量标签 <span id='lblSYDL'> 或 <span id='Label1'>"
            else:
                power_text = power_span.get_text().strip()

                if re.match(r'^\d+\.\d+$', power_text):
                    result = f"{dorm_name} (ID: {dorm_id}) 的剩余电量为: {power_text} 度"
                    
                    # 检查今天是否已经记录过
                    should_save = self.should_save_daily_record(dorm_id)
                    if should_save:
                        self.save_to_database(dorm_id, dorm_name, float(power_text))
                    else:
                        print(f"今天已经记录过 {dorm_id} 的电量，跳过保存")
                elif power_text == "暂不支持查询":
                    result = f"提示：{dorm_name} (ID: {dorm_id}) 不支持电量查询"
                else:
                    result = f"警告：{dorm_name} (ID: {dorm_id}) 电量格式异常 '{power_text}'"

            self.root.after(0, self.update_query_result, result)

        except requests.RequestException as e:
            self.root.after(0, self.update_query_result, f"网络请求错误: {str(e)}")
        except Exception as e:
            self.root.after(0, self.update_query_result, f"程序出错: {str(e)}")
            
            
    def should_save_daily_record(self, dorm_id):
        """检查今天是否已经保存过该宿舍的记录"""
        conn = sqlite3.connect('electricity_data.db')
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute(
            "SELECT COUNT(*) FROM electricity_records "
            "WHERE dorm_id = ? AND DATE(query_time) = ?",
            (dorm_id, today)
        )
        
        count = cursor.fetchone()[0]
        conn.close()
        
        return count == 0
    
    
    def update_query_result(self, result):
        """更新查询结果"""
        self.query_result.delete(1.0, tk.END)
        self.query_result.insert(tk.END, result)

    def save_to_database(self, dorm_id, dorm_name, power):
        """保存查询结果到数据库"""
        conn = sqlite3.connect('electricity_data.db')
        cursor = conn.cursor()
        current_time = time.strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(
            "INSERT INTO electricity_records (dorm_id, dorm_name, query_time, power) VALUES (?, ?, ?, ?)",
            (dorm_id, dorm_name, current_time, power)
        )
        conn.commit()
        conn.close()

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

        self.recharge_info.config(text=f"即将前往 {dorm_name} (ID: {dorm_id}, 类型: {dorm_type}) 的充值页面")

        if messagebox.askyesno("确认充值", f"是否跳转到 {dorm_name} 的充值页面?"):
            threading.Thread(target=webbrowser.open, args=(recharge_url,), daemon=True).start()
            messagebox.showinfo("提示", "已为你打开充值页面，如需返回请关闭浏览器或切换窗口")

    def clear_all(self):
        """清空所有输入和结果"""
        self.search_entry.delete(0, tk.END)
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)
        self.query_result.delete(1.0, tk.END)
        self.recharge_info.config(text="请先搜索并选择宿舍")
        self.query_button.config(state=tk.DISABLED)
        self.recharge_button.config(state=tk.DISABLED)
        self.create_widget_button.config(state=tk.DISABLED)

    def create_desktop_widget(self):
        """创建桌面小摆件并关闭主程序"""
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

        # 启动桌面小摆件程序
        python_executable = sys.executable
        subprocess.Popen([python_executable, "widget.py"])
        
        # 关闭主程序
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = DormitoryPowerChecker(root)
    root.mainloop()