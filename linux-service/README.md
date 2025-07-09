# XSYUDormPowerSpider 电费监控服务（Linux自动化部署版）

本项目为西安石油大学宿舍电费自动监控与推送服务，支持一键自动化部署为 systemd 服务。

---

## 🚀 一键自动化部署

1. **进入项目目录**
   ```bash
   cd XSYUDormPowerSpider_linux
   ```

2. **赋予自动化脚本执行权限**
   ```bash
   chmod +x install_auto.sh
   ```

3. **运行自动化部署脚本**
   ```bash
   ./install_auto.sh
   ```
   > 脚本会自动完成依赖安装、虚拟环境创建、systemd服务生成与启动，无需手动干预。

4. **查看服务状态和日志**
   ```bash
   sudo systemctl status power-monitor.service
   sudo journalctl -u power-monitor.service -f
   ```

---

## 🛠️ 服务管理常用命令

- 启动服务：
  ```bash
  sudo systemctl start power-monitor.service
  ```
- 停止服务：
  ```bash
  sudo systemctl stop power-monitor.service
  ```
- 重启服务：
  ```bash
  sudo systemctl restart power-monitor.service
  ```
- 查看状态：
  ```bash
  sudo systemctl status power-monitor.service
  ```
- 查看日志：
  ```bash
  sudo journalctl -u power-monitor.service -f
  ```
- 设置开机自启：
  ```bash
  sudo systemctl enable power-monitor.service
  ```

---

## ⚙️ 配置说明

- **主配置文件**：`config.yaml`
- **宿舍数据文件**：`dorm_rooms_2025.csv`
- **依赖文件**：`requirements_service.txt`

### config.yaml 示例
```yaml
monitor:
  schedule_time: "19:00"  # 每天定时监控时间
  global_threshold: 10.0   # 全局电量阈值

notifications:
  server_chan:
    enabled: true
    sendkey: "你的Server酱SENDKEY"

dormitories:
  - dorm_id: "101640017"
    dorm_name: "1号楼-101"
    dorm_type: "1"
    low_power_threshold: 10.0
    enabled: true
```

> **注意：dorm_id、dorm_name、dorm_type 请直接从 dorm_rooms_2025.csv 查找和复制，避免填写错误。**



---


## 📢 联系与支持
如有问题或建议，欢迎在GitHub提issue，或直接联系开发者。
qq:376742095

---

## 许可证
MIT License