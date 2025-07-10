import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

class Scraper:
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
        url = f"https://hydz.xsyu.edu.cn/wxpay/settlementlist.aspx?type={dorm_type}&xid={dorm_id}"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            records = []
            
            data_texts = soup.stripped_strings
            data_list = list(data_texts)

            power_indices = [i for i, x in enumerate(data_list) if x == "剩余电量"]
            time_indices = [i for i, x in enumerate(data_list) if x == "抄表时间"]

            for i in range(min(len(power_indices), len(time_indices))):
                power_index = power_indices[i] + 1
                time_index = time_indices[i] + 1
                if power_index < len(data_list) and time_index < len(data_list):
                    power_str = data_list[power_index]
                    time_str = data_list[time_index]
                    
                    try:
                        power_val = float(power_str)
                        # Keep the full datetime object, do not convert to date
                        datetime_val = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                        records.append((datetime_val, power_val))
                    except (ValueError, TypeError):
                        continue

            if not records:
                return [], "在页面上找到了数据，但解析失败。页面结构可能已更新。"

            # Return the raw records, sorted ascending by time
            return sorted(records, key=lambda x: x[0]), None

        except requests.exceptions.RequestException as e:
            return [], f"网络请求失败: {e}"
        except Exception as e:
            return [], f"处理数据时发生未知错误: {e}" 