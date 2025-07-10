#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
电费监控服务 (Linux Service)
功能：
1. 定时查询指定宿舍的电费
2. 当电费低于阈值时发送通知
3. 支持多种通知方式
4. 作为Linux服务运行
"""

import requests
from bs4 import BeautifulSoup
import re
import time
import yaml
import logging
import threading
from datetime import datetime, timedelta
import csv
import os
import sys
import signal
from typing import Dict, List, Tuple, Optional
import schedule

class PowerMonitorService:
    def __init__(self, config_file: str = "config.yaml"):
        """
        初始化电费监控服务
        
        Args:
            config_file: YAML配置文件路径
        """
        self.config_file = config_file
        # 先用基础配置初始化logger，防止后面用到self.logger时报错
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        self.config = self.load_config()      # 先加载配置
        self.setup_logging()                  # 再根据配置重设日志
        self.dormitories = self.load_dormitory_data()
        self.notified_dorms = set()
        self.is_running = False
        self.scheduler_thread = None
        # 信号处理
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        self.logger.info("电费监控服务初始化完成")
    
    def signal_handler(self, signum, frame):
        """信号处理函数"""
        self.logger.info(f"收到信号 {signum}，正在停止服务...")
        self.stop_service()
        sys.exit(0)
    
    def load_config(self) -> dict:
        """加载YAML配置文件"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    self.logger.info(f"成功加载配置文件: {self.config_file}")
                    return config
            else:
                self.logger.error(f"配置文件不存在: {self.config_file}")
                sys.exit(1)
        except Exception as e:
            self.logger.error(f"加载配置文件失败: {e}")
            sys.exit(1)
    
    def setup_logging(self):
        """设置日志"""
        monitor_config = self.config.get("monitor", {})
        logging_config = monitor_config.get("logging", {})
        
        if not logging_config.get("enabled", True):
            return
            
        log_level = getattr(logging, logging_config.get("level", "INFO").upper())
        
        # 创建logs目录
        os.makedirs("logs", exist_ok=True)
        
        # 获取日志文件路径
        log_file = logging_config.get("file", "logs/power_monitor_{date}.log")
        log_file = log_file.replace("{date}", datetime.now().strftime('%Y%m%d'))
        
        # 配置日志
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def load_dormitory_data(self) -> Dict[str, Tuple[str, str]]:
        """加载宿舍数据"""
        dormitories = {}
        try:
            # 检查是否是打包后的可执行文件
            if getattr(sys, 'frozen', False):
                base_path = sys._MEIPASS
            else:
                base_path = os.path.dirname(os.path.abspath(__file__))

            file_path = os.path.join(base_path, 'dorm_rooms_2025.csv')
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    dorm_id = row['room_code']
                    dorm_name = f"{row['building']}-{row['room_number']}"
                    dorm_type = row['dorm_type']
                    dormitories[dorm_id] = (dorm_name, dorm_type)
                    
        except Exception as e:
            self.logger.error(f"加载宿舍数据失败: {e}")
            
        return dormitories
    
    def query_power(self, dorm_id: str, dorm_name: str, dorm_type: str) -> Optional[float]:
        """
        查询宿舍电量
        
        Args:
            dorm_id: 宿舍ID
            dorm_name: 宿舍名称
            dorm_type: 宿舍类型
            
        Returns:
            电量值（度），查询失败返回None
        """
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
                self.logger.error(f"未找到电量标签: {dorm_name}")
                return None
                
            power_text = power_span.get_text().strip()

            if re.match(r'^\d+\.\d+$', power_text):
                power = float(power_text)
                self.logger.info(f"{dorm_name} 电量: {power} 度")
                return power
            elif power_text == "暂不支持查询":
                self.logger.warning(f"{dorm_name} 不支持电量查询")
                return None
            else:
                self.logger.error(f"{dorm_name} 电量格式异常: '{power_text}'")
                return None

        except requests.RequestException as e:
            self.logger.error(f"网络请求错误 ({dorm_name}): {e}")
            return None
        except Exception as e:
            self.logger.error(f"查询电量失败 ({dorm_name}): {e}")
            return None
    
    def send_server_chan_notification(self, dorm_name: str, power: float, dorm_id: str, dorm_type: str, threshold: float) -> bool:
        """发送Server酱通知"""
        server_chan_config = self.config.get("notifications", {}).get("server_chan", {})
        
        if not server_chan_config.get("enabled", False):
            return False
            
        sendkey = server_chan_config.get("sendkey", "")
        if not sendkey:
            self.logger.error("未配置SENDKEY，无法发送通知")
            return False
            
        try:
            url = server_chan_config.get("url", "https://sctapi.ftqq.com/{sendkey}.send").format(sendkey=sendkey)
            
            # 使用模板生成通知内容
            templates = self.config.get("templates", {})
            title = templates.get("title", "⚠️ 电量不足提醒 - {dorm_name}").format(dorm_name=dorm_name)
            content = templates.get("content", "").format(
                dorm_name=dorm_name,
                power=power,
                threshold=threshold,
                time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                dorm_id=dorm_id,
                dorm_type=dorm_type
            )
            
            data = {
                "title": title,
                "desp": content
            }
            
            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            if result.get("code") == 0:
                self.logger.info(f"Server酱通知发送成功: {dorm_name}")
                return True
            else:
                self.logger.error(f"Server酱通知发送失败: {result.get('message', '未知错误')}")
                return False
                
        except Exception as e:
            self.logger.error(f"发送Server酱通知失败: {e}")
            return False
    
    def send_custom_webhook_notification(self, dorm_name: str, power: float, dorm_id: str, dorm_type: str, threshold: float) -> bool:
        """发送自定义Webhook通知"""
        webhook_config = self.config.get("notifications", {}).get("custom_webhook", {})
        
        if not webhook_config.get("enabled", False):
            return False
            
        try:
            url = webhook_config.get("url", "")
            method = webhook_config.get("method", "POST")
            headers = webhook_config.get("headers", {})
            template = webhook_config.get("template", {})
            
            # 使用模板生成通知内容
            title = template.get("title", "电量不足提醒").format(dorm_name=dorm_name)
            content = template.get("content", "").format(
                dorm_name=dorm_name,
                power=power,
                threshold=threshold
            )
            
            data = {
                "title": title,
                "content": content,
                "dorm_name": dorm_name,
                "power": power,
                "threshold": threshold,
                "dorm_id": dorm_id,
                "dorm_type": dorm_type,
                "timestamp": datetime.now().isoformat()
            }
            
            if method.upper() == "POST":
                response = requests.post(url, json=data, headers=headers, timeout=10)
            else:
                response = requests.get(url, params=data, headers=headers, timeout=10)
                
            response.raise_for_status()
            self.logger.info(f"自定义Webhook通知发送成功: {dorm_name}")
            return True
                
        except Exception as e:
            self.logger.error(f"发送自定义Webhook通知失败: {e}")
            return False
    
    def send_notification(self, dorm_name: str, power: float, dorm_id: str, dorm_type: str, threshold: float) -> bool:
        """
        发送通知（支持多种通知方式）
        
        Args:
            dorm_name: 宿舍名称
            power: 电量
            dorm_id: 宿舍ID
            dorm_type: 宿舍类型
            threshold: 阈值
            
        Returns:
            发送成功返回True，失败返回False
        """
        success = False
        
        # 发送Server酱通知
        if self.send_server_chan_notification(dorm_name, power, dorm_id, dorm_type, threshold):
            success = True
            
        # 发送自定义Webhook通知
        if self.send_custom_webhook_notification(dorm_name, power, dorm_id, dorm_type, threshold):
            success = True
            
        return success
    
    def should_send_notification(self, dorm_id: str) -> bool:
        """检查是否应该发送通知（避免重复通知）"""
        monitor_config = self.config.get("monitor", {})
        cooldown_seconds = monitor_config.get("notification_cooldown_seconds", 3600)
        
        # 检查是否在冷却期内
        if dorm_id in self.notified_dorms:
            return False
            
        return True
    
    def mark_notified(self, dorm_id: str):
        """标记已发送通知"""
        self.notified_dorms.add(dorm_id)
        
        # 设置定时器，在冷却期后移除标记
        monitor_config = self.config.get("monitor", {})
        cooldown_seconds = monitor_config.get("notification_cooldown_seconds", 3600)
        
        def remove_notification_mark():
            time.sleep(cooldown_seconds)
            self.notified_dorms.discard(dorm_id)
            self.logger.info(f"重置 {dorm_id} 的通知状态")
            
        threading.Thread(target=remove_notification_mark, daemon=True).start()
    
    def monitor_single_dorm(self, dorm_config: dict):
        """监控单个宿舍"""
        dorm_id = dorm_config["dorm_id"]
        dorm_name = dorm_config["dorm_name"]
        dorm_type = dorm_config["dorm_type"]
        enabled = dorm_config.get("enabled", True)
        
        if not enabled:
            self.logger.debug(f"跳过禁用的宿舍: {dorm_name}")
            return
        
        # 获取该宿舍的阈值，如果没有设置则使用全局阈值
        monitor_config = self.config.get("monitor", {})
        threshold = dorm_config.get("low_power_threshold", monitor_config.get("global_threshold", 10.0))
        
        # 查询电量
        power = self.query_power(dorm_id, dorm_name, dorm_type)
        
        if power is None:
            return
            
        # 检查是否低于阈值
        if power < threshold:
            self.logger.warning(f"{dorm_name} 电量不足: {power} 度 < {threshold} 度")
            
            # 检查是否应该发送通知
            if self.should_send_notification(dorm_id):
                if self.send_notification(dorm_name, power, dorm_id, dorm_type, threshold):
                    self.mark_notified(dorm_id)
            else:
                self.logger.info(f"{dorm_name} 在冷却期内，跳过通知")
        else:
            self.logger.info(f"{dorm_name} 电量充足: {power} 度")
    
    def run_monitoring_task(self):
        """执行监控任务"""
        self.logger.info("开始执行监控任务")
        
        try:
            dormitories = self.config.get("dormitories", [])
            
            if not dormitories:
                self.logger.warning("没有配置要监控的宿舍")
                return
            
            enabled_dorms = [dorm for dorm in dormitories if dorm.get("enabled", True)]
            self.logger.info(f"开始监控 {len(enabled_dorms)} 个宿舍")
            
            for dorm_config in enabled_dorms:
                if not self.is_running:
                    break
                self.monitor_single_dorm(dorm_config)
                time.sleep(2)  # 间隔2秒，避免请求过于频繁
            
            self.logger.info("监控任务完成")
            
        except Exception as e:
            self.logger.error(f"监控任务出错: {e}")
    
    def start_service(self):
        """启动服务"""
        if self.is_running:
            self.logger.warning("服务已在运行中")
            return
            
        self.is_running = True
        
        # 设置定时任务
        schedule_time = self.config.get("monitor", {}).get("schedule_time", "19:00")
        schedule.every().day.at(schedule_time).do(self.run_monitoring_task)
        
        # 启动调度器线程
        self.scheduler_thread = threading.Thread(target=self.run_scheduler, daemon=True)
        self.scheduler_thread.start()
        
        self.logger.info(f"电费监控服务已启动，将在每天 {schedule_time} 执行监控任务")
    
    def run_scheduler(self):
        """运行调度器"""
        while self.is_running:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次
    
    def stop_service(self):
        """停止服务"""
        self.is_running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        self.logger.info("电费监控服务已停止")
    
    def run_once(self):
        """立即执行一次监控任务"""
        self.logger.info("立即执行监控任务")
        self.run_monitoring_task()


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="电费监控服务")
    parser.add_argument("--config", "-c", default="config.yaml", help="配置文件路径")
    parser.add_argument("--once", action="store_true", help="立即执行一次监控任务")
    parser.add_argument("--daemon", action="store_true", help="以守护进程模式运行")
    
    args = parser.parse_args()
    
    # 创建监控服务
    monitor = PowerMonitorService(args.config)
    
    if args.once:
        # 立即执行一次
        monitor.run_once()
    else:
        # 启动服务
        monitor.start_service()
        
        try:
            # 保持运行
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            monitor.stop_service()


if __name__ == "__main__":
    main() 