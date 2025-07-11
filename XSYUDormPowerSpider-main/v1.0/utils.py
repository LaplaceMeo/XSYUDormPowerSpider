# 工具函数
import subprocess
import sys
import platform
import os
from database import DatabaseManager
from datetime import datetime, timedelta

def open_main_app():
    """打开主程序"""
    python_executable = sys.executable
    try:
        subprocess.Popen([python_executable, "main_app.py"])
    except Exception as e:
        print(f"Error opening main app: {e}")

def open_recharge_page(dorm_id, dorm_type):
    """打开充值页面"""
    import webbrowser
    recharge_url = f"https://hydz.xsyu.edu.cn/wxpay/homeinfo.aspx?xid={dorm_id}&type={dorm_type}&opid=a"
    webbrowser.open(recharge_url)

def predict_remaining_days(dorm_id):
    """
    根据历史用电数据预测剩余电量可用天数。

    Args:
        dorm_id (str): 宿舍的唯一标识ID。

    Returns:
        tuple: (预测状态, 预测天数或提示信息)
               状态可以是 'predict', 'sufficient', 'not_enough_data', 'error'。
    """
    db_manager = DatabaseManager()
    # 获取最近30天的数据以提高效率和相关性
    start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    records = db_manager.get_records_by_dorm_id(dorm_id, start_date=start_date)
    db_manager.close()

    if len(records) < 2:
        return ('not_enough_data', "历史数据不足 (至少需要2天)")

    # 将记录转换为 (datetime, power)
    parsed_records = []
    for rec in records:
        try:
            # 兼容多种可能的日期时间格式
            time_str, power = rec
            dt_object = datetime.fromisoformat(time_str)
            parsed_records.append((dt_object, power))
        except (ValueError, TypeError):
            continue # 跳过格式不正确的记录

    if len(parsed_records) < 2:
        return ('not_enough_data', "有效的历史数据不足")
    
    # 使用最早和最新的记录进行计算
    latest_record = parsed_records[-1]
    earliest_record = parsed_records[0]

    current_power = latest_record[1]
    
    # 计算时间差（天数）和电量消耗
    time_difference = latest_record[0] - earliest_record[0]
    days_elapsed = time_difference.total_seconds() / (3600 * 24)
    
    power_consumed = earliest_record[1] - latest_record[1]

    # 避免除以零或时间过短导致的不准确预测
    if days_elapsed < 0.5:
        return ('not_enough_data', "数据时间跨度太短")

    if power_consumed <= 0:
        return ('sufficient', "电量充足，无需担心！")

    # 计算日均消耗
    daily_consumption_rate = power_consumed / days_elapsed
    
    if daily_consumption_rate <= 0:
        return ('sufficient', "电量充足，无需担心！")

    # 预测剩余天数
    days_remaining = current_power / daily_consumption_rate
    
    return ('predict', f"{days_remaining:.1f}")