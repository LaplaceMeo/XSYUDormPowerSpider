import network
import urequests as requests
from machine import Pin, I2C
from ssd1306 import SSD1306_I2C
import time
import gc

# WiFi configuration
WIFI_SSID = ""  #这里改为WIFI账号
WIFI_PASSWORD = "" #这里改为你的WIFI密码

# OLED display configuration (I2C interface)
OLED_WIDTH = 128
OLED_HEIGHT = 64
OLED_SCL_PIN = 22  # GPIO22 connected to OLED SCL
OLED_SDA_PIN = 21  # GPIO21 connected to OLED SDA

def connect_wifi():
    """Connect to WiFi network"""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    # If already connected, return directly
    if wlan.isconnected():
        print("Already connected to WiFi")
        return True
    
    print(f"Connecting to WiFi: {WIFI_SSID}")
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)
    
    # Wait for connection with 60-second timeout
    for i in range(60):
        if wlan.isconnected():
            print(f"WiFi connection successful! IP address: {wlan.ifconfig()[0]}")
            return True
        time.sleep(1)
        print(".", end="")
    
    print("WiFi connection timed out!")
    return False

def init_oled():
    """Initialize OLED display"""
    try:
        i2c = I2C(0, scl=Pin(OLED_SCL_PIN), sda=Pin(OLED_SDA_PIN), freq=400000)
        oled = SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, i2c)
        oled.fill(0)  # Clear screen
        oled.text("ESP32 OLED Init", 0, 0)
        oled.show()
        return oled
    except Exception as e:
        print(f"OLED initialization failed: {str(e)}")
        return None

def get_remaining_power():
    """Scrape remaining electricity for dormitory 20414"""
    url = f"http://hydz.xsyu.edu.cn/wxpay/homeinfo.aspx?xid=20414&type=2&opid=a"   #这里改为你宿舍的请求链接
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://hydz.xsyu.edu.cn/wxpay/homeinfo.aspx",
    }
    
    try:
        # Send request
        response = requests.get(url, headers=headers, timeout=15)
        response_text = response.text
        response.close()  # Close connection manually to avoid memory leak
        
        # Parse HTML - Use regular expressions instead of BeautifulSoup
        import re
        power_match = re.search(r'<span[^>]*id=["\'](lblSYDL|Label1)["\'][^>]*>([^<]+)</span>', response_text)
        
        if power_match:
            power_text = power_match.group(2).strip()
            
            # Validate format
            if re.match(r'^\d+\.\d+$', power_text):
                return float(power_text)
            elif power_text == "暂不支持查询":
                print("Info: Electricity query not supported for this dorm")
                return None
            else:
                print(f"Warning: Abnormal electricity format '{power_text}'")
                return None
        else:
            print("Error: Remaining power label not found")
            return None
            
    except Exception as e:
        print(f"Program error: {str(e)}")
        return None

def format_time():
    """Format current time in MicroPython"""
    t = time.localtime()
    return f"{t[0]}-{t[1]:02d}-{t[2]:02d} {t[3]:02d}:{t[4]:02d}"

def display_on_oled(oled, power):
    """Display electricity information on OLED"""
    if not oled:
        return
    
    oled.fill(0)  # Clear screen
    
    oled.text("Dorm Power Monitor", 0, 0)
    oled.hline(0, 10, OLED_WIDTH, 1)  # Horizontal line
    
    if power is not None:
        oled.text(f"Dorm: 20414", 0, 20)
        oled.text(f"Remaining: {power} kWh", 0, 35)
        oled.text(format_time(), 0, 50)  # Use custom time formatting
        
        # Low power indicator
        if power < 5:
            oled.text("Warning: Low Power!", 0, 45)
    else:
        oled.text("Failed to get power", 0, 25)
        oled.text("Check network connection", 0, 40)
    
    oled.show()

def main():
    """Main program"""
    # Initialize OLED
    oled = init_oled()
    if not oled:
        print("OLED initialization failed, program exiting")
        return
    
    # Connect to WiFi
    if not connect_wifi():
        display_on_oled(oled, None)
        return
    
    # Scrape electricity data
    power = get_remaining_power()
    
    # Display result
    display_on_oled(oled, power)
    
    # Free memory
    gc.collect()
    
    print("Program execution completed")

if __name__ == "__main__":
    main()