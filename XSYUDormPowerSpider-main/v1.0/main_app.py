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
from datetime import datetime
import os
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.scrolled import ScrolledText
from ttkbootstrap.widgets import DateEntry
from thefuzz import process
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates
from datetime import timedelta
import pandas as pd

try:
    plt.rcParams['font.sans-serif'] = ['SimHei']
    plt.rcParams['axes.unicode_minus'] = False
except Exception as e:
    print(f"设置中文字体失败: {e}")

from database import DatabaseManager
from scraper import Scraper
from config import ConfigManager
from utils import predict_remaining_days # 导入预测函数

class ChartDrawer:
    """用于绘制图表的基类，采用延迟初始化来避免资源泄露"""
    def __init__(self, master_tab, style):
        self.master = master_tab
        self.style = style
        self.fig, self.ax, self.canvas, self.line = None, None, None, None

    def _initialize_chart(self):
        """延迟初始化图表和画布，仅在需要时调用。"""
        if self.canvas is None:
            self.fig, self.ax = plt.subplots(figsize=(10, 5))
            self.canvas = FigureCanvasTkAgg(self.fig, master=self.master)
            self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            self._setup_hover_annotation()

    def _setup_hover_annotation(self):
        """设置鼠标悬停注释的通用逻辑"""
        annot = self.ax.annotate("", xy=(0,0), xytext=(20,20), textcoords="offset points",
                                 bbox=dict(boxstyle="round", fc="w", ec="k", lw=1),
                                 arrowprops=dict(arrowstyle="->"))
        annot.set_visible(False)

        def update_annotation(ind):
            if self.line is None: return
            pos = self.line.get_xydata()[ind["ind"][0]]
            annot.xy = pos
            annot.set_text(self.format_hover_text(pos))
            annot.get_bbox_patch().set_alpha(0.8)

        def on_hover(event):
            if event.inaxes == self.ax and self.line:
                contains, ind = self.line.contains(event)
                if contains:
                    update_annotation(ind)
                    annot.set_visible(True)
                    self.fig.canvas.draw_idle()
                elif annot.get_visible():
                    annot.set_visible(False)
                    self.fig.canvas.draw_idle()
        
        self.fig.canvas.mpl_connect("motion_notify_event", on_hover)

    def format_hover_text(self, pos):
        """格式化悬停时显示的文本（由子类实现）"""
        raise NotImplementedError

    def draw(self, data):
        self._initialize_chart() # 确保图表已创建
        self.ax.clear()
        # 子类将在这里实现具体的绘图逻辑
        self.canvas.draw()
        
class ConsumptionChart(ChartDrawer):
    """用电量消耗分析图表"""
    def format_hover_text(self, pos):
        date_str = mdates.num2date(pos[0]).strftime('%Y-%m-%d %H:%M')
        return f"截至 {date_str}\n消耗: {pos[1]:.2f} 度"

    def draw(self, data):
        self._initialize_chart()
        self.ax.clear()

        if data is None or data.empty:
            self.ax.text(0.5, 0.5, "当前粒度无消耗数据", ha='center', va='center', fontsize=12)
            self.line = None
        else:
            self.line, = self.ax.plot(data.index, data.values, marker='o', linestyle='-', color=self.style.colors.primary)
        
        self.ax.set_title('每小时用电量消耗', fontsize=16)
        self.ax.set_xlabel('日期时间', fontsize=12)
        self.ax.set_ylabel('消耗电量 (度)', fontsize=12)
        self.ax.grid(True, which='both', linestyle='--', linewidth=0.5)
        self.fig.autofmt_xdate()
        self.fig.tight_layout()
        self.canvas.draw()

class RemainingChart(ChartDrawer):
    """剩余电量趋势图表"""
    def format_hover_text(self, pos):
        date_str = mdates.num2date(pos[0]).strftime('%Y-%m-%d %H:%M')
        return f"{date_str}\n剩余: {pos[1]:.2f} 度"
    
    def draw(self, data):
        self._initialize_chart()
        self.ax.clear()

        if not data:
            self.ax.text(0.5, 0.5, "无剩余电量历史数据", ha='center', va='center', fontsize=12)
            self.line = None
        else:
            dates = [mdates.date2num(datetime.fromisoformat(rec[0])) for rec in data]
            powers = [rec[1] for rec in data]
            self.line, = self.ax.plot(dates, powers, marker='o', linestyle='-', color=self.style.colors.info)
        
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
        self.ax.set_title('历史剩余电量趋势', fontsize=16)
        self.ax.set_xlabel('日期时间', fontsize=12)
        self.ax.set_ylabel('剩余电量 (度)', fontsize=12)
        self.ax.grid(True, which='both', linestyle='--', linewidth=0.5)
        self.fig.autofmt_xdate()
        self.fig.tight_layout()
        self.canvas.draw()

class HistoryAnalysisWindow(tk.Toplevel):
    """一个独立的、用于显示历史数据分析的窗口，负责管理自己的资源。"""
    def __init__(self, parent, dorm_name, dorm_id, scraper, style, id_mapping):
        super().__init__(parent)
        self.title(f"{dorm_name} - 历史用电分析")
        self.geometry("900x750")

        self.scraper = scraper
        self.style = style
        self.dorm_id = dorm_id
        self.id_mapping = id_mapping

        # --- UI Setup ---
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=tk.YES, padx=10, pady=10)

        consumption_tab = ttk.Frame(notebook)
        remaining_tab = ttk.Frame(notebook)
        notebook.add(consumption_tab, text=' 用电量分析 ')
        notebook.add(remaining_tab, text=' 剩余电量趋势 ')

        control_frame = ttk.Frame(consumption_tab)
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(control_frame, text="统计粒度:").pack(side=tk.LEFT, padx=(0, 10))
        self.interval_var = tk.StringVar(value="24")
        intervals = {"每日": "24", "每12小时": "12", "每6小时": "6"}
        for text, value in intervals.items():
            ttk.Radiobutton(control_frame, text=text, variable=self.interval_var, value=value).pack(side=tk.LEFT)
        
        chart_container = ttk.Frame(consumption_tab)
        chart_container.pack(fill=tk.BOTH, expand=tk.YES)

        prediction_frame = ttk.LabelFrame(self, text="💡 用电趋势预测", padding="15", bootstyle="success")
        prediction_frame.pack(fill=tk.X, padx=10, pady=(10, 0))
        self.prediction_result_label = ttk.Label(prediction_frame, text="正在分析...", font=("微软雅黑", 14), bootstyle="inverse-success")
        self.prediction_result_label.pack(pady=10)

        self.consumption_chart = ConsumptionChart(chart_container, self.style)
        self.remaining_chart = RemainingChart(remaining_tab, self.style)

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        threading.Thread(target=self.initial_load_and_draw, daemon=True).start()

    def on_close(self):
        """自定义关闭事件处理函数，确保Matplotlib图形对象被正确关闭以释放内存。"""
        # 增加判断，确保 fig 存在才 close
        if self.consumption_chart.fig:
            plt.close(self.consumption_chart.fig)
        if self.remaining_chart.fig:
            plt.close(self.remaining_chart.fig)
        self.destroy()

    def process_consumption_data(self, records, interval_hours):
        if not records: return pd.Series(dtype='float64')
        try:
            df = pd.DataFrame(records, columns=['time', 'power'])
            df['time'] = pd.to_datetime(df['time'])
            df = df.set_index('time').sort_index()
            df['consumption'] = -df['power'].diff()
            # 使用 'h' 替换已弃用的 'H'
            consumption_series = df['consumption'].resample(f'{interval_hours}h').sum()
            return consumption_series[consumption_series > 0]
        except Exception:
            return pd.Series(dtype='float64')

    def update_prediction_display(self):
        status, result = predict_remaining_days(self.dorm_id)
        def _update_ui():
            if status == 'predict': text = f"预测剩余电量大约还能使用: {result} 天"
            elif status == 'sufficient': text = f"分析结果: {result}"
            else: text = f"无法预测: {result}"
            self.prediction_result_label.config(text=text)
        self.after(0, _update_ui)

    def initial_load_and_draw(self):
        api_records, error_message = self.scraper.get_historical_power(self.dorm_id, self.id_mapping[self.dorm_id][1])
        if error_message or not api_records:
            self.after(0, lambda: messagebox.showerror("加载失败", error_message or "未返回任何历史数据", parent=self))
            self.after(0, self.on_close) # 调用 on_close 来确保清理
            return

        self.update_prediction_display()

        fourteen_days_ago = datetime.now() - timedelta(days=14)
        recent_records = [rec for rec in api_records if datetime.fromisoformat(rec[0]) >= fourteen_days_ago]
        self.after(0, lambda: self.remaining_chart.draw(recent_records))

        def on_interval_change(*args):
            interval = int(self.interval_var.get())
            processed_data = self.process_consumption_data(api_records, interval)
            self.after(0, lambda: self.consumption_chart.draw(processed_data))
        
        self.interval_var.trace_add("write", on_interval_change)
        self.after(0, on_interval_change)

class DormitoryPowerChecker:
    def __init__(self, root):
        self.config_manager = ConfigManager()
        self.db_manager = DatabaseManager()
        self.scraper = Scraper()
        self.root = root
        
        initial_theme = self.config_manager.get_setting('Theme', 'current_theme', 'litera')
        self.style = ttk.Style(theme=initial_theme)
        initial_geometry = self.config_manager.get_setting('Window', 'geometry', '900x800')
        self.root.geometry(initial_geometry)
        
        self.root.title("宿舍电量查询与充值系统")
        self.dormitories = []
        self.id_mapping = {}

        self.create_widgets()
        self.create_menu()
        self.load_dormitory_data()
        
    def load_dormitory_data(self):
        try:
            base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
            file_path = os.path.join(base_path, 'dorm_rooms_2025.csv')
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = f"{row['building']}-{row['room_number']}"
                    self.dormitories.append({'name': name, 'id': row['room_code'], 'type': row['dorm_type']})
                    self.id_mapping[row['room_code']] = (name, row['dorm_type'])
        except Exception as e:
            messagebox.showerror("错误", f"无法读取文件: {str(e)}")

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=tk.YES)
        ttk.Label(main_frame, text="宿舍电量查询与充值系统", font=("微软雅黑", 20, "bold"), bootstyle="primary").pack(pady=(0, 20))
        search_frame = ttk.Frame(main_frame)
        search_frame.pack(fill=tk.X, pady=5)
        ttk.Label(search_frame, text="输入房间号进行搜索:", font=("微软雅黑", 12)).pack(side=tk.LEFT, padx=(0, 10))
        self.search_entry = ttk.Entry(search_frame, font=("微软雅黑", 12), width=50)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=tk.YES)
        self.placeholder_text = "输入宿舍楼-房间号，如11-123"
        self.search_entry.insert(0, self.placeholder_text)
        self.search_entry.config(foreground="grey")
        self.search_entry.bind("<KeyRelease>", self.on_search)
        self.search_entry.bind("<FocusIn>", self.on_entry_focus_in)
        self.search_entry.bind("<FocusOut>", self.on_entry_focus_out)
        result_frame = ttk.LabelFrame(main_frame, text="搜索结果", padding="10", bootstyle="info")
        result_frame.pack(fill=tk.BOTH, expand=tk.YES, pady=10)
        self.scrollbar = ttk.Scrollbar(result_frame, bootstyle="round-primary")
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.result_tree = ttk.Treeview(result_frame, columns=("name", "id"), show="headings", yscrollcommand=self.scrollbar.set, bootstyle="primary")
        self.result_tree.heading("name", text="宿舍名称"); self.result_tree.heading("id", text="宿舍ID")
        self.result_tree.column("name", width=400, anchor=tk.W); self.result_tree.column("id", width=200, anchor=tk.W)
        self.result_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=tk.YES)
        self.scrollbar.config(command=self.result_tree.yview)
        self.result_tree.bind("<Double-1>", lambda e: self.query_power())
        query_frame = ttk.LabelFrame(main_frame, text="电量查询结果", padding="10", bootstyle="info")
        query_frame.pack(fill=tk.X, pady=10)
        self.query_result = ScrolledText(query_frame, height=8, font=("微软雅黑", 10), relief="flat")
        self.query_result.pack(fill=tk.X, expand=tk.YES)
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        self.query_button = ttk.Button(button_frame, text="🔍 查询电量", command=self.query_power, state=tk.DISABLED, bootstyle="success")
        self.query_button.pack(side=tk.LEFT, padx=5, ipady=5)
        self.recharge_button = ttk.Button(button_frame, text="💳 前往充值", command=self.recharge_dormitory, state=tk.DISABLED, bootstyle="info")
        self.recharge_button.pack(side=tk.LEFT, padx=5, ipady=5)
        self.create_widget_button = ttk.Button(button_frame, text="🐱 创建摆件", command=self.create_desktop_widget, state=tk.DISABLED, bootstyle="warning")
        self.create_widget_button.pack(side=tk.LEFT, padx=5, ipady=5)
        self.history_button = ttk.Button(button_frame, text="📊 查看历史", command=self.show_history_graph, state=tk.DISABLED, bootstyle="secondary")
        self.history_button.pack(side=tk.LEFT, padx=5, ipady=5)
        ttk.Button(button_frame, text="🗑️ 清空", command=self.clear_all, bootstyle="danger").pack(side=tk.RIGHT, padx=5, ipady=5)

    def create_menu(self):
        menu_bar = ttk.Menu(self.root)
        self.root.config(menu=menu_bar)
        theme_menu = ttk.Menu(menu_bar, tearoff=False)
        menu_bar.add_cascade(label="🎨 主题", menu=theme_menu)
        theme_map = {'litera': '文学 (亮)', 'cosmo': '宇宙 (亮)', 'flatly': '扁平 (亮)', 'journal': '日志 (亮)', 'lumen': '流明 (亮)', 'minty': '薄荷 (亮)', 'pulse': '脉冲 (亮)', 'sandstone': '砂岩 (亮)', 'united': '联合 (亮)', 'yeti': '雪人 (亮)', 'cyborg': '赛博格 (暗)', 'darkly': '暗黑 (暗)', 'solar': '太阳 (暗)', 'superhero': '超英 (暗)', 'vapor': '蒸汽波 (暗)'}
        for name_en, name_zh in theme_map.items():
            theme_menu.add_command(label=name_zh, command=lambda t=name_en: self.change_theme(t))
        widget_style_menu = ttk.Menu(menu_bar, tearoff=False)
        menu_bar.add_cascade(label="摆件风格", menu=widget_style_menu)
        for style_name in ['默认', '猫娘']:
            widget_style_menu.add_command(label=style_name, command=lambda s=style_name: self.set_widget_style(s))

    def set_widget_style(self, style_name):
        self.config_manager.set_setting('Widget', 'style', style_name)
        messagebox.showinfo("设置成功", f"桌面摆件风格已设置为: {style_name}\n\n下次创建摆件时将生效。", parent=self.root)

    def on_entry_focus_in(self, event):
        if self.search_entry.get() == self.placeholder_text:
            self.search_entry.delete(0, "end"); self.search_entry.config(foreground=self.style.colors.get('fg'))

    def on_entry_focus_out(self, event):
        if not self.search_entry.get():
            self.search_entry.insert(0, self.placeholder_text); self.search_entry.config(foreground="grey")

    def change_theme(self, theme_name):
        self.style.theme_use(theme_name)
        self.config_manager.set_setting('Theme', 'current_theme', theme_name)

    def on_search(self, event=None):
        for item in self.result_tree.get_children(): self.result_tree.delete(item)
        search_text = self.search_entry.get().strip()
        if not search_text or search_text == self.placeholder_text:
            return self.toggle_buttons(tk.DISABLED)
        results = process.extract(search_text, [d['name'] for d in self.dormitories], limit=50)
        found_dorms = [d for name, score in results if score > 70 for d in self.dormitories if d['name'] == name]
        for dorm in found_dorms: self.result_tree.insert("", tk.END, values=(dorm['name'], dorm['id']))
        self.toggle_buttons(tk.NORMAL if found_dorms else tk.DISABLED)

    def toggle_buttons(self, state):
        self.query_button.config(state=state); self.recharge_button.config(state=state)
        self.create_widget_button.config(state=state); self.history_button.config(state=state)

    def query_power(self):
        item = self.result_tree.selection()
        if not item: return messagebox.showwarning("警告", "请先从列表中选择一个宿舍")
        dorm_name, dorm_id = self.result_tree.item(item, "values")[:2]
        dorm_type = self.id_mapping[dorm_id][1]
        self.query_result.delete(1.0, tk.END)
        self.query_result.insert(tk.END, f"正在查询 {dorm_name} (ID: {dorm_id}) 的电量...\n"); self.root.update()
        threading.Thread(target=self.query_power_in_thread, args=(dorm_id, dorm_name, dorm_type), daemon=True).start()

    def query_power_in_thread(self, dorm_id, dorm_name, dorm_type):
        # 保存宿舍选择
        dorm_selection_parts = dorm_name.split('-')
        if len(dorm_selection_parts) == 3:
            area, building, room = dorm_selection_parts
            self.config_manager.save_selected_dorm(area.strip(), building.strip(), room.strip())

        try:
            self.root.after(0, self.query_result.delete, '1.0', tk.END)
            self.root.after(0, self.query_result.insert, tk.END, f"正在查询 {dorm_name} 的电量...\n")
            self.root.update()

            power_text, error_message = self.scraper.get_power(dorm_id, dorm_type)
            if error_message:
                result = f"查询失败：{error_message}"
            else:
                # 成功获取电量后，立即进行预测
                pred_status, pred_result = predict_remaining_days(dorm_id)
                if pred_status == 'predict':
                    prediction_text = f"💡 预测：剩余电量大约还能使用 {pred_result} 天。"
                elif pred_status == 'sufficient':
                    prediction_text = f"💡 预测：{pred_result}"
                else:
                    prediction_text = "💡 预测：历史数据不足，暂时无法预测。"
                
                result = f"{dorm_name} (ID: {dorm_id}) 的剩余电量为: {power_text} 度\n{prediction_text}"
                
                try:
                    # 使用正则表达式从power_text中提取数字用于保存
                    power_value = float(re.search(r'(\d+\.?\d*)', power_text).group(1))
                    self.db_manager.save_record(dorm_id, dorm_name, power_value)
                except (ValueError, TypeError, AttributeError):
                    pass
            
            self.root.after(0, lambda: (self.query_result.insert(tk.END, f"{result}\n\n"), self.query_result.see(tk.END)))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("查询失败", f"查询过程中发生错误: {e}"))
            self.root.after(0, self.toggle_buttons, tk.NORMAL)

    def recharge_dormitory(self):
        item = self.result_tree.selection()
        if not item: return messagebox.showwarning("警告", "请先选择一个宿舍")
        dorm_name, dorm_id = self.result_tree.item(item, "values")[:2]
        dorm_type = self.id_mapping[dorm_id][1]
        recharge_url = f"https://hydz.xsyu.edu.cn/wxpay/homeinfo.aspx?xid={dorm_id}&type={dorm_type}&opid=a"
        if messagebox.askyesno("确认充值", f"是否跳转到 {dorm_name} 的充值页面?"): webbrowser.open(recharge_url)

    def clear_all(self):
        self.search_entry.delete(0, tk.END)
        for item in self.result_tree.get_children(): self.result_tree.delete(item)
        self.query_result.delete(1.0, tk.END)
        self.toggle_buttons(tk.DISABLED)
        self.on_entry_focus_out(None)

    def create_desktop_widget(self):
        item = self.result_tree.selection()
        if not item: return messagebox.showwarning("警告", "请先选择一个宿舍")
        dorm_name, dorm_id = self.result_tree.item(item, "values")[:2]
        dorm_type = self.id_mapping[dorm_id][1]
        
        widget_script_path = os.path.join(os.path.dirname(__file__), 'widget.py')
        
        try:
            # 使用 Popen 在一个完全独立的进程中启动小摆件
            # 并通过命令行参数传递必要的信息
            subprocess.Popen([sys.executable, widget_script_path, dorm_id, dorm_type, dorm_name])
            messagebox.showinfo("成功", "桌面摆件已启动！\n您现在可以关闭主窗口，摆件会继续运行。", parent=self.root)
        except Exception as e:
            messagebox.showerror("启动失败", f"无法启动小摆件进程: {e}", parent=self.root)

    def show_history_graph(self):
        item = self.result_tree.selection()
        if not item:
            return messagebox.showwarning("提示", "请先在列表中选择一个宿舍。")
        dorm_name, dorm_id = self.result_tree.item(item, "values")[:2]
        # 创建一个独立的、自管理的分析窗口实例
        HistoryAnalysisWindow(self.root, dorm_name, dorm_id, self.scraper, self.style, self.id_mapping)

    def on_closing(self):
        self.config_manager.set_setting('Window', 'geometry', self.root.winfo_geometry())
        self.config_manager.save_config()
        self.db_manager.close()
        self.root.destroy()

def main():
    try:
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