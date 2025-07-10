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
        self.load_dormitory_data()
        self.create_widgets()
        self.create_menu()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

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
        main_frame.pack(fill=BOTH, expand=YES)
        ttk.Label(main_frame, text="宿舍电量查询与充值系统", font=("微软雅黑", 20, "bold"), bootstyle="primary").pack(pady=(0, 20))
        search_frame = ttk.Frame(main_frame)
        search_frame.pack(fill=X, pady=5)
        ttk.Label(search_frame, text="输入房间号进行搜索:", font=("微软雅黑", 12)).pack(side=LEFT, padx=(0, 10))
        self.search_entry = ttk.Entry(search_frame, font=("微软雅黑", 12), width=50)
        self.search_entry.pack(side=LEFT, fill=X, expand=YES)
        self.placeholder_text = "输入宿舍楼-房间号，如11-123"
        self.search_entry.insert(0, self.placeholder_text)
        self.search_entry.config(foreground="grey")
        self.search_entry.bind("<KeyRelease>", self.on_search)
        self.search_entry.bind("<FocusIn>", self.on_entry_focus_in)
        self.search_entry.bind("<FocusOut>", self.on_entry_focus_out)
        result_frame = ttk.LabelFrame(main_frame, text="搜索结果", padding="10", bootstyle="info")
        result_frame.pack(fill=BOTH, expand=YES, pady=10)
        self.scrollbar = ttk.Scrollbar(result_frame, bootstyle="round-primary")
        self.scrollbar.pack(side=RIGHT, fill=Y)
        self.result_tree = ttk.Treeview(result_frame, columns=("name", "id"), show="headings", yscrollcommand=self.scrollbar.set, bootstyle="primary")
        self.result_tree.heading("name", text="宿舍名称"); self.result_tree.heading("id", text="宿舍ID")
        self.result_tree.column("name", width=400, anchor=W); self.result_tree.column("id", width=200, anchor=W)
        self.result_tree.pack(side=LEFT, fill=BOTH, expand=YES)
        self.scrollbar.config(command=self.result_tree.yview)
        self.result_tree.bind("<Double-1>", lambda e: self.query_power())
        query_frame = ttk.LabelFrame(main_frame, text="电量查询结果", padding="10", bootstyle="info")
        query_frame.pack(fill=X, pady=10)
        self.query_result = ScrolledText(query_frame, height=8, font=("微软雅黑", 10), relief="flat")
        self.query_result.pack(fill=X, expand=YES)
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=X, pady=10)
        self.query_button = ttk.Button(button_frame, text="🔍 查询电量", command=self.query_power, state=DISABLED, bootstyle="success")
        self.query_button.pack(side=LEFT, padx=5, ipady=5)
        self.recharge_button = ttk.Button(button_frame, text="💳 前往充值", command=self.recharge_dormitory, state=DISABLED, bootstyle="info")
        self.recharge_button.pack(side=LEFT, padx=5, ipady=5)
        self.create_widget_button = ttk.Button(button_frame, text="🐱 创建摆件", command=self.create_desktop_widget, state=DISABLED, bootstyle="warning")
        self.create_widget_button.pack(side=LEFT, padx=5, ipady=5)
        self.history_button = ttk.Button(button_frame, text="📊 查看历史", command=self.show_history_graph, state=DISABLED, bootstyle="secondary")
        self.history_button.pack(side=LEFT, padx=5, ipady=5)
        ttk.Button(button_frame, text="🗑️ 清空", command=self.clear_all, bootstyle="danger").pack(side=RIGHT, padx=5, ipady=5)

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
            return self.toggle_buttons(DISABLED)
        results = process.extract(search_text, [d['name'] for d in self.dormitories], limit=50)
        found_dorms = [d for name, score in results if score > 70 for d in self.dormitories if d['name'] == name]
        for dorm in found_dorms: self.result_tree.insert("", tk.END, values=(dorm['name'], dorm['id']))
        self.toggle_buttons(NORMAL if found_dorms else DISABLED)

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
        power_text, error_message = self.scraper.get_power(dorm_id, dorm_type)
        if error_message: result = f"查询失败：{error_message}"
        else:
            result = f"{dorm_name} (ID: {dorm_id}) 的剩余电量为: {power_text} 度"
            try: self.db_manager.save_record(dorm_id, dorm_name, float(power_text))
            except (ValueError, TypeError): pass
        self.root.after(0, lambda: (self.query_result.insert(tk.END, f"{result}\n"), self.query_result.see(tk.END)))

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
        self.toggle_buttons(DISABLED)
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

        graph_window = tk.Toplevel(self.root)
        graph_window.title(f"{dorm_name} - 历史用电分析")
        graph_window.geometry("900x750")

        notebook = ttk.Notebook(graph_window)
        notebook.pack(fill=BOTH, expand=YES, padx=10, pady=10)

        consumption_tab = ttk.Frame(notebook)
        remaining_tab = ttk.Frame(notebook)
        notebook.add(consumption_tab, text=' 用电量分析 ')
        notebook.add(remaining_tab, text=' 剩余电量趋势 ')

        all_records = []

        def setup_hover_annotation_for_ax(ax, line_ref_provider, text_formatter):
            annot = ax.annotate("", xy=(0,0), xytext=(20,20), textcoords="offset points",
                                bbox=dict(boxstyle="round", fc="w", ec="k", lw=1),
                                arrowprops=dict(arrowstyle="->"))
            annot.set_visible(False)

            def update_annotation(ind, line):
                pos = line.get_xydata()[ind["ind"][0]]
                annot.xy = pos
                annot.set_text(text_formatter(pos))
                annot.get_bbox_patch().set_alpha(0.8)

            def on_hover(event):
                if event.inaxes == ax:
                    line = line_ref_provider()
                    if line is None: return
                    contains, ind = line.contains(event)
                    if contains:
                        update_annotation(ind, line)
                        annot.set_visible(True)
                        fig.canvas.draw_idle()
                    elif annot.get_visible():
                        annot.set_visible(False)
                        fig.canvas.draw_idle()
            return on_hover

        def setup_consumption_tab():
            top_frame = ttk.Frame(consumption_tab, padding=(0, 10, 0, 5))
            top_frame.pack(fill=X)
            ttk.Label(top_frame, text="统计粒度:").pack(side=LEFT, padx=(0, 10))
            
            interval_var = tk.StringVar(value="24")
            intervals = [("每日", "24"), ("每12小时", "12"), ("每6小时", "6")]
            for text, value in intervals:
                ttk.Radiobutton(top_frame, text=text, variable=interval_var, value=value).pack(side=LEFT, padx=5)

            chart_frame = ttk.Frame(consumption_tab)
            chart_frame.pack(fill=BOTH, expand=YES, pady=5)
            fig, ax = plt.subplots(figsize=(10, 6), dpi=100)
            canvas = FigureCanvasTkAgg(fig, master=chart_frame)
            canvas.get_tk_widget().pack(fill=BOTH, expand=YES)

            table_frame = ttk.Frame(consumption_tab, padding=(0, 5, 0, 0))
            table_frame.pack(fill=X)
            table = ttk.Treeview(table_frame, columns=("period", "consumption"), show="headings", height=5)
            table.heading("period", text="时间段")
            table.heading("consumption", text="用电量 (度)")
            table.pack(side=LEFT, fill=X, expand=YES)
            scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=table.yview)
            scrollbar.pack(side=RIGHT, fill=Y)
            table.configure(yscrollcommand=scrollbar.set)
            
            line = None
            def get_line(): return line
            
            def consumption_formatter(pos):
                date_str = mdates.num2date(pos[0]).strftime('%Y-%m-%d %H:%M')
                return f"截至 {date_str}\n消耗: {pos[1]:.2f} 度"
            
            fig.canvas.mpl_connect("motion_notify_event", setup_hover_annotation_for_ax(ax, get_line, consumption_formatter))
            
            def process_and_display():
                if not all_records: return
                interval_hours = int(interval_var.get())
                df = pd.DataFrame(all_records, columns=['time', 'power'])
                df.set_index('time', inplace=True)
                
                power_resampled = df['power'].resample(f'{interval_hours}h').first().interpolate(method='linear') if len(df) >= 2 else pd.Series(dtype='float64')
                consumption = -power_resampled.diff()
                
                draw_chart(consumption)
                update_table(consumption)
            
            interval_var.trace_add("write", lambda name, index, mode: process_and_display())

            def draw_chart(consumption_series):
                nonlocal line
                ax.clear()
                
                data_to_plot = consumption_series.iloc[1:].dropna()
                if data_to_plot.empty:
                    ax.text(0.5, 0.5, "数据不足，无法计算该粒度下的用电量", ha='center', va='center')
                    ax.set_title(f"{dorm_name} - 用电量分析")
                    line = None
                else:
                    line, = ax.plot(data_to_plot.index, data_to_plot.values, marker='o', linestyle='-')
                    interval_text = interval_var.get()
                    ax.set_title(f"{dorm_name} - 每{interval_text}小时用电趋势", fontsize=16)
                
                ax.set_xlabel('日期', fontsize=12)
                ax.set_ylabel('用电量 (度)', fontsize=12)
                ax.grid(True, which='both', linestyle='--', linewidth=0.5)
                fig.autofmt_xdate(ha='right')
                canvas.draw()

            def update_table(consumption_series):
                table.delete(*table.get_children())
                for timestamp, value in consumption_series.iloc[1:].iloc[::-1].items():
                    if pd.notna(value):
                        end_time = timestamp
                        start_time = end_time - timedelta(hours=int(interval_var.get()))
                        period_str = f"{start_time.strftime('%m-%d %H:%M')} 至 {end_time.strftime('%m-%d %H:%M')}"
                        table.insert("", "end", values=(period_str, f"{value:.2f}"))
            
            return process_and_display, (ax, canvas)

        def setup_remaining_tab():
            chart_frame = ttk.Frame(remaining_tab)
            chart_frame.pack(fill=BOTH, expand=YES, padx=0, pady=5)
            fig, ax = plt.subplots(figsize=(10, 6), dpi=100)
            canvas = FigureCanvasTkAgg(fig, master=chart_frame)
            canvas.get_tk_widget().pack(fill=BOTH, expand=YES)
            
            line = None
            def get_line(): return line

            def remaining_formatter(pos):
                date_str = mdates.num2date(pos[0]).strftime('%Y-%m-%d %H:%M')
                return f"{date_str}\n剩余: {pos[1]:.2f} 度"
                
            fig.canvas.mpl_connect("motion_notify_event", setup_hover_annotation_for_ax(ax, get_line, remaining_formatter))

            def draw_chart(records):
                nonlocal line
                ax.clear()
                if not records:
                    ax.text(0.5, 0.5, "无历史数据", ha='center', va='center')
                    line = None
                else:
                    dates = [rec[0] for rec in records]
                    power_values = [rec[1] for rec in records]
                    line, = ax.plot(dates, power_values, marker='o', linestyle='-')
                    ax.set_title(f"{dorm_name} - 剩余电量趋势", fontsize=16)
                
                ax.set_xlabel('日期', fontsize=12)
                ax.set_ylabel('剩余电量 (度)', fontsize=12)
                ax.grid(True, which='both', linestyle='--', linewidth=0.5)
                fig.autofmt_xdate(ha='right')
                canvas.draw()
            
            return draw_chart
        
        consumption_processor, (ax_consum, can_consum) = setup_consumption_tab()
        remaining_drawer = setup_remaining_tab()

        def initial_load():
            nonlocal all_records
            ax_consum.text(0.5, 0.5, '正在从服务器获取官方历史数据...', ha='center', va='center', fontsize=14)
            can_consum.draw()
            
            api_records, error_message = self.scraper.get_historical_power(dorm_id, self.id_mapping[dorm_id][1])
            
            if error_message or not api_records:
                messagebox.showerror("加载失败", error_message or "未返回任何历史数据", parent=graph_window)
                ax_consum.clear(); can_consum.draw()
                remaining_drawer([])
                return

            all_records = sorted(api_records, key=lambda x: x[0])
            consumption_processor()
            remaining_drawer(all_records)

        threading.Thread(target=initial_load, daemon=True).start()
            
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