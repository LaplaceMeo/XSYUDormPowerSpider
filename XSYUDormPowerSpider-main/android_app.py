import kivy
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
import sys
import os

# 将项目主目录添加到系统路径，以便 Kivy 应用能找到其他模块
# 在 buildozer 环境中, __file__ 的路径可能是相对于应用根目录的
try:
    project_path = os.path.dirname(os.path.abspath(__file__))
    # 在 buildozer 打包后，目录结构可能会改变，我们假定核心代码在 'v1' 文件夹
    # 因此，我们需要能够导入 'v1' 目录下的模块
    # sys.path.append(project_path)
except NameError:
    # 如果在某些上下文中 __file__ 未定义, 则使用当前工作目录
    project_path = os.getcwd()

sys.path.append(project_path)
sys.path.append(os.path.join(project_path, 'v1'))


# 现在可以从项目主目录下的模块导入
from v1.scraper import get_latest_power_data
from v1.config import ConfigManager # 导入ConfigManager
from v1.database import get_db_connection

class DormPowerApp(App):
    def build(self):
        self.layout = BoxLayout(orientation='vertical', padding=30, spacing=10)
        
        self.power_label = Label(text='点击刷新获取电量...', font_size='24sp')
        self.layout.add_widget(self.power_label)
        
        refresh_button = Button(text='刷新', size_hint_y=None, height=50)
        refresh_button.bind(on_press=self.refresh_power)
        self.layout.add_widget(refresh_button)
        
        return self.layout

    def refresh_power(self, instance):
        self.power_label.text = "正在查询..."
        try:
            config_manager = ConfigManager()

            username, password = config_manager.get_credentials()
            if not username or not password:
                self.power_label.text = "错误: 未找到凭据\n请先在桌面应用登录一次"
                return

            dorm_info = config_manager.load_selected_dorm()
            if not dorm_info:
                self.power_label.text = "错误: 未选择宿舍\n请先在桌面应用查询一次"
                return

            area, building, room = dorm_info['area'], dorm_info['building'], dorm_info['room']

            # 数据库路径处理
            app_root = self.get_running_app().user_data_dir
            db_path = os.path.join(app_root, 'electricity_data.db')
            source_db = os.path.join(project_path, '..', 'electricity_data.db')
            if not os.path.exists(db_path) and os.path.exists(source_db):
                import shutil
                shutil.copy(source_db, db_path)

            # 获取电量数据
            conn = get_db_connection(db_path)
            power_data = get_latest_power_data(conn, area, building, room, username, password)
            conn.close()

            if power_data:
                latest_record = power_data[-1]
                remaining_power = latest_record[2]
                self.power_label.text = f'当前剩余电量: {remaining_power} kWh'
            else:
                self.power_label.text = '无法获取电量数据'
        except Exception as e:
            import traceback
            self.power_label.text = f'查询出错:\n{e}\n{traceback.format_exc()}'

if __name__ == '__main__':
    DormPowerApp().run() 