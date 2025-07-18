import configparser
import os

class ConfigManager:
    def __init__(self, config_name='config.ini'):
        app_dir = os.path.join(os.path.expanduser('~'), '.XSYUDormPowerSpider')
        if not os.path.exists(app_dir):
            os.makedirs(app_dir)
        self.config_path = os.path.join(app_dir, config_name)
        
        self.config = configparser.ConfigParser()
        # 如果配置文件存在，则读取
        if os.path.exists(self.config_path):
            self.config.read(self.config_path, encoding='utf-8')
        else:
            # 否则，创建默认配置
            self._create_default_config()

    def _create_default_config(self):
        """创建默认的配置文件"""
        self.config['Theme'] = {'current_theme': 'litera'}
        self.config['Window'] = {'geometry': '900x800'}
        self.config['Widget'] = {'style': '默认'}
        self.config['Credentials'] = {'username': '', 'password': ''} # 新增
        self.save_config()

    def get_setting(self, section, option, fallback=None):
        """获取配置项"""
        return self.config.get(section, option, fallback=fallback)

    def set_setting(self, section, option, value):
        """设置配置项"""
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, option, str(value))

    def save_credentials(self, username, password):
        """保存凭据到配置文件"""
        self.set_setting('Credentials', 'username', username)
        self.set_setting('Credentials', 'password', password)
        self.save_config()

    def get_credentials(self):
        """从配置文件获取凭据"""
        username = self.get_setting('Credentials', 'username', '')
        password = self.get_setting('Credentials', 'password', '')
        return username, password

    def save_selected_dorm(self, area, building, room):
        """保存用户选择的宿舍信息"""
        self.set_setting('DormSelection', 'area', area)
        self.set_setting('DormSelection', 'building', building)
        self.set_setting('DormSelection', 'room', room)
        self.save_config()

    def load_selected_dorm(self):
        """加载用户选择的宿舍信息"""
        if not self.config.has_section('DormSelection'):
            return None
        return {
            'area': self.get_setting('DormSelection', 'area'),
            'building': self.get_setting('DormSelection', 'building'),
            'room': self.get_setting('DormSelection', 'room')
        }

    def save_config(self):
        """保存配置到文件"""
        with open(self.config_path, 'w', encoding='utf-8') as configfile:
            self.config.write(configfile) 