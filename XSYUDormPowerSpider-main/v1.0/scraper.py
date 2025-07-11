import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

class Scraper:
    def __init__(self):
        # 增加 User-Agent，模拟浏览器访问，这是解决问题的关键
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.session = requests.Session()

    def get_power(self, dorm_id, dorm_type):
        """
        根据宿舍ID和类型，爬取剩余电量。
        返回一个元组 (power_text, error_message)。
        成功时 power_text 有值，error_message 为 None。
        失败时 power_text 为 None，error_message 有值。
        """
        try:
            url = f"http://hydz.xsyu.edu.cn/wxpay/homeinfo.aspx?xid={dorm_id}&type={dorm_type}&opid=a"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Referer": "https://hydz.xsyu.edu.cn/wxpay/homeinfo.aspx",
            }

            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()  # 如果请求失败（如404, 500），则抛出异常
            response.encoding = 'utf-8'

            soup = BeautifulSoup(response.text, 'html.parser')

            power_span = soup.find('span', id='lblSYDL') or soup.find('span', id='Label1')
            if not power_span:
                return None, "错误：未能在页面上找到电量信息，网站结构可能已更新。"

            power_text = power_span.get_text(strip=True)
            if re.match(r'^\d+(\.\d+)?$', power_text):
                return power_text, None
            else:
                return None, f"错误：获取到的电量格式不正确 ({power_text})。"

        except requests.exceptions.RequestException as e:
            return None, f"网络错误：无法连接到电量查询服务器。({e})"
        except Exception as e:
            return None, f"未知错误：{e}"

    def get_historical_power(self, dorm_id, dorm_type):
        """
        从官方接口获取详细的历史电量记录。
        此版本使用 stripped_strings 进行解析，更加健壮。
        """
        history_url = f"https://hydz.xsyu.edu.cn/wxpay/settlementlist.aspx?type={dorm_type}&xid={dorm_id}"
        try:
            response = requests.get(history_url, headers=self.headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            records = []
            # 使用 stripped_strings 获取页面所有纯文本内容，并转换为列表
            strings = list(soup.stripped_strings)

            # 遍历列表，寻找"剩余电量"和"抄表时间"的组合
            for i, text in enumerate(strings):
                if text == '剩余电量' and i + 2 < len(strings) and strings[i+2] == '抄表时间':
                    power_str = strings[i+1]
                    time_str = strings[i+3]
                    
                    try:
                        power_val = float(power_str)
                        time_obj = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                        # 转换为与之前逻辑一致的ISO格式字符串
                        records.append((time_obj.isoformat(), power_val))
                    except (ValueError, TypeError):
                        # 如果某个记录解析失败，则跳过，继续解析下一个
                        continue
            
            if not records:
                return None, "在官方页面未找到任何有效的历史数据记录。"

            # 按时间升序排序
            records.sort(key=lambda x: x[0])
            return records, None

        except requests.exceptions.RequestException as e:
            return None, f"获取历史数据时网络请求失败: {e}"
        except Exception as e:
            return None, f"解析历史数据时发生未知错误: {e}" 