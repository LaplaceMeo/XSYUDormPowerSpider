# 数据库操作模块
import sqlite3

def get_latest_power(dorm_id):
    """获取指定宿舍的最新电量记录"""
    conn = sqlite3.connect('electricity_data.db')
    cursor = conn.cursor()
    cursor.execute(
        "SELECT power, query_time FROM electricity_records "
        "WHERE dorm_id = ? ORDER BY query_time DESC LIMIT 1",
        (dorm_id,)
    )
    result = cursor.fetchone()
    conn.close()
    return result

def get_power_history(dorm_id, limit=10):
    """获取指定宿舍的电量历史记录"""
    conn = sqlite3.connect('electricity_data.db')
    cursor = conn.cursor()
    cursor.execute(
        "SELECT power, query_time FROM electricity_records "
        "WHERE dorm_id = ? ORDER BY query_time DESC LIMIT ?",
        (dorm_id, limit)
    )
    results = cursor.fetchall()
    conn.close()
    return results


def get_daily_average_power(dorm_id, days=7):
    """获取近7天的每日平均电量"""
    conn = sqlite3.connect('electricity_data.db')
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT DATE(query_time) as date, AVG(power) as avg_power "
        "FROM electricity_records "
        "WHERE dorm_id = ? "
        "GROUP BY DATE(query_time) "
        "ORDER BY date DESC "
        "LIMIT ?",
        (dorm_id, days)
    )
    
    results = cursor.fetchall()
    conn.close()
    
    return results