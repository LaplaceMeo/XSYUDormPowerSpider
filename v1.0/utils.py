# 工具函数
import subprocess
import sys

def open_main_app():
    """打开主程序"""
    python_executable = sys.executable
    subprocess.Popen([python_executable, "main_app.py"])

def open_recharge_page(dorm_id, dorm_type):
    """打开充值页面"""
    import webbrowser
    recharge_url = f"https://hydz.xsyu.edu.cn/wxpay/homeinfo.aspx?xid={dorm_id}&type={dorm_type}&opid=a"
    webbrowser.open(recharge_url)