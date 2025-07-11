# 数据库操作模块
import sqlite3
from datetime import datetime
import os
import threading

class DatabaseManager:
    def __init__(self, db_name='electricity_data.db'):
        app_dir = os.path.join(os.path.expanduser('~'), '.XSYUDormPowerSpider')
        if not os.path.exists(app_dir):
            os.makedirs(app_dir)
        self.db_path = os.path.join(app_dir, db_name)
        self.local = threading.local()  # 使用线程局部存储
        self.init_database()

    def get_connection(self):
        """为每个线程获取独立的数据库连接"""
        if not hasattr(self.local, 'conn'):
            self.local.conn = sqlite3.connect(self.db_path)
        return self.local.conn

    def init_database(self):
        """初始化数据表（使用一个临时连接）"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS electricity_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dorm_id TEXT,
                dorm_name TEXT,
                query_time DATETIME,
                power REAL
            )
        ''')
        conn.commit()

    def should_save_daily_record(self, dorm_id):
        """检查今天是否已经为该宿舍记录过数据"""
        conn = self.get_connection()
        cursor = conn.cursor()
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('''
            SELECT 1 FROM electricity_records 
            WHERE dorm_id = ? AND DATE(query_time) = ?
            LIMIT 1
        ''', (dorm_id, today))
        return cursor.fetchone() is None

    def save_record(self, dorm_id, dorm_name, power):
        """保存一条新的电量记录"""
        if self.should_save_daily_record(dorm_id):
            conn = self.get_connection()
            cursor = conn.cursor()
            query_time = datetime.now()
            cursor.execute('''
                INSERT INTO electricity_records (dorm_id, dorm_name, query_time, power)
                VALUES (?, ?, ?, ?)
            ''', (dorm_id, dorm_name, query_time, power))
            conn.commit()
            return True
        return False

    def get_records_by_dorm_id(self, dorm_id, start_date=None, end_date=None):
        """根据宿舍ID和可选的日期范围获取历史记录"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = '''
            SELECT query_time, power FROM electricity_records
            WHERE dorm_id = ?
        '''
        params = [dorm_id]

        if start_date:
            query += ' AND DATE(query_time) >= ?'
            params.append(start_date)
        
        if end_date:
            query += ' AND DATE(query_time) <= ?'
            params.append(end_date)
            
        query += ' ORDER BY query_time ASC' # 按时间升序排列，方便绘图

        cursor.execute(query, tuple(params))
        return cursor.fetchall()

    def close(self):
        """关闭当前线程的数据库连接"""
        if hasattr(self.local, 'conn'):
            self.local.conn.close()
            del self.local.conn