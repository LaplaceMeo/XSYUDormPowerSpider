# -*- coding: utf-8 -*-
"""
@File: DormElectrics.py
@Description: 本脚本专为 ESP32 开发板设计，使用 MicroPython 运行。
             功能：连接指定WiFi，从西安石油大学水电服务平台抓取特定宿舍的剩余电量，
             并将其显示在 SSD1306 OLED 屏幕上。
@Author: LaplaceHe
@Date: 2025-07-12
"""

import network
import urequests as requests
from machine import Pin, I2C
from ssd1306 import SSD1306_I2C
import time
import gc
import re

# ==============================================================================
# ============================== 用户配置区 =====================================
# ==============================================================================

# 请在此处填入您的WiFi名称和密码
WIFI_SSID = ""      # 例如: "MyHomeWiFi"
WIFI_PASSWORD = ""  # 例如: "password123"

# 请在此处填入您宿舍的水电查询URL
# 获取方法：电脑登录水电查询网站，F12打开开发者工具，选择宿舍后，在网络(Network)中找到 homeinfo.aspx 开头的请求，复制其完整链接。
DORM_QUERY_URL = "http://hydz.xsyu.edu.cn/wxpay/homeinfo.aspx?xid=20414&type=2&opid=a"

# OLED 显示屏的 I2C 引脚配置
OLED_WIDTH = 128
OLED_HEIGHT = 64
OLED_SCL_PIN = 22  # OLED SCL 引脚连接到 ESP32 的 GPIO22
OLED_SDA_PIN = 21  # OLED SDA 引脚连接到 ESP32 的 GPIO21

# ==============================================================================
# ============================ 程序核心代码 =====================================
# ==============================================================================

def connect_wifi():
    """
    连接到指定的WiFi网络。
    会进行60秒的连接尝试，超时则失败。
    """
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    # 如果已经连接，则直接返回成功
    if wlan.isconnected():
        print("WiFi 已连接。")
        return True
    
    print(f"正在连接到WiFi: {WIFI_SSID}...")
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)
    
    # 等待连接，超时时间为60秒
    for _ in range(60):
        if wlan.isconnected():
            print(f"WiFi连接成功! IP地址: {wlan.ifconfig()[0]}")
            return True
        time.sleep(1)
        print(".", end="")
    
    print("\nWiFi连接超时！")
    return False

def init_oled():
    """
    初始化I2C接口的SSD1306 OLED显示屏。
    返回一个OLED对象，失败则返回None。
    """
    try:
        i2c = I2C(0, scl=Pin(OLED_SCL_PIN), sda=Pin(OLED_SDA_PIN), freq=400000)
        oled = SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, i2c)
        oled.fill(0)  # 清空屏幕
        oled.text("OLED Init...", 0, 0)
        oled.show()
        return oled
    except Exception as e:
        print(f"OLED初始化失败: {str(e)}")
        return None

def get_remaining_power(url):
    """
    从指定URL抓取并解析宿舍剩余电量。
    使用正则表达式解析，以减少内存占用。
    """
    # 模拟浏览器请求头，防止被服务器拒绝
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://hydz.xsyu.edu.cn/wxpay/homeinfo.aspx",
    }
    
    try:
        print("正在发送网络请求...")
        response = requests.get(url, headers=headers, timeout=15)
        response_text = response.text
        response.close()  # 在MicroPython中，手动关闭连接是个好习惯
        print("请求成功，正在解析数据...")

        # 使用正则表达式从HTML中直接提取电量信息
        # 目标是 <span id="lblSYDL">...</span> 或 <span id="Label1">...</span> 标签内的内容
        power_match = re.search(r'<span[^>]*id=["\'](lblSYDL|Label1)["\'][^>]*>([^<]+)</span>', response_text)
        
        if power_match:
            power_text = power_match.group(2).strip()
            
            # 检查提取到的文本是否为纯数字格式
            if re.match(r'^\d+\.?\d*$', power_text):
                return float(power_text)
            else:
                print(f"警告: 获取到非数字电量值 '{power_text}'")
                return None
        else:
            print("错误: 在HTML响应中未找到电量信息标签。")
            return None
            
    except Exception as e:
        print(f"抓取电量时发生程序错误: {str(e)}")
        return None

def format_time():
    """
    获取并格式化当前时间。
    返回 "年-月-日 时:分" 格式的字符串。
    """
    t = time.localtime()
    return f"{t[0]}-{t[1]:02d}-{t[2]:02d} {t[3]:02d}:{t[4]:02d}"

def display_on_oled(oled, power, url):
    """
    在OLED屏幕上显示电量信息和当前时间。
    """
    if not oled:
        return
    
    oled.fill(0)  # 每次显示前清空屏幕
    
    oled.text("Dorm Power Monitor", 0, 0)
    oled.hline(0, 10, OLED_WIDTH, 1)  # 绘制一条分割线
    
    # 从URL中提取宿舍ID用于显示
    dorm_id_match = re.search(r'xid=(\d+)', url)
    dorm_id = dorm_id_match.group(1) if dorm_id_match else "N/A"

    if power is not None:
        oled.text(f"Dorm: {dorm_id}", 0, 20)
        oled.text(f"Power: {power} kWh", 0, 35)
        
        # 当电量低于10度时，显示警告信息
        if power < 10:
            oled.text("Warning: Low Power!", 0, 50)
    else:
        oled.text(f"Dorm: {dorm_id}", 0, 20)
        oled.text("Failed to get data.", 0, 35)
    
    oled.show()
    print("OLED屏幕已刷新。")

def main():
    """
    主程序执行流程。
    """
    oled = init_oled()
    if not oled:
        print("OLED初始化失败，程序退出。")
        return
    
    if connect_wifi():
        power = get_remaining_power(DORM_QUERY_URL)
        display_on_oled(oled, power, DORM_QUERY_URL)
    else:
        # WiFi连接失败时，在屏幕上显示错误信息
        oled.fill(0)
        oled.text("WiFi Connect Fail", 0, 25)
        oled.text("Check SSID/PASS", 0, 40)
        oled.show()

    # 在内存受限的设备上，手动触发垃圾回收是一个好习惯
    gc.collect()
    print(f"执行完毕。当前剩余内存: {gc.mem_free()} bytes")

if __name__ == "__main__":
    main()