# 数据库操作模块
import sqlite3
from datetime import datetime
import os

class DatabaseManager:
    def __init__(self, db_name='electricity_data.db'):
        self.db_path = self.get_db_path(db_name)
        self.conn = None
        self.cursor = None
        self.connect()
        self.init_database()

    def get_db_path(self, db_name):
        # 将数据库文件放在用户目录下的.XSYUDormPowerSpider文件夹中，避免权限问题
        app_dir = os.path.join(os.path.expanduser('~'), '.XSYUDormPowerSpider')
        if not os.path.exists(app_dir):
            os.makedirs(app_dir)
        return os.path.join(app_dir, db_name)

    def connect(self):
        """建立数据库连接"""
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()

    def init_database(self):
        """初始化数据表"""
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS electricity_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dorm_id TEXT,
                dorm_name TEXT,
                query_time DATETIME,
                power REAL
            )
        ''')
        self.conn.commit()

    def should_save_daily_record(self, dorm_id):
        """检查今天是否已经为该宿舍记录过数据"""
        today = datetime.now().strftime('%Y-%m-%d')
        self.cursor.execute('''
            SELECT 1 FROM electricity_records 
            WHERE dorm_id = ? AND DATE(query_time) = ?
            LIMIT 1
        ''', (dorm_id, today))
        return self.cursor.fetchone() is None

    def save_record(self, dorm_id, dorm_name, power):
        """保存一条新的电量记录"""
        if self.should_save_daily_record(dorm_id):
            query_time = datetime.now()
            self.cursor.execute('''
                INSERT INTO electricity_records (dorm_id, dorm_name, query_time, power)
                VALUES (?, ?, ?, ?)
            ''', (dorm_id, dorm_name, query_time, power))
            self.conn.commit()
            return True
        return False

    def get_records_by_dorm_id(self, dorm_id, limit=30):
        """根据宿舍ID获取历史记录"""
        self.cursor.execute('''
            SELECT query_time, power FROM electricity_records
            WHERE dorm_id = ?
            ORDER BY query_time DESC
            LIMIT ?
        ''', (dorm_id, limit))
        return self.cursor.fetchall()

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()