#!/bin/bash

set -e

# 自动获取用户名和项目路径
USER=$(whoami)
PROJECT_DIR=$(pwd)
SERVICE_NAME=power-monitor.service
VENV_DIR="$PROJECT_DIR/venv"
PYTHON_BIN="$VENV_DIR/bin/python"
PIP_BIN="$VENV_DIR/bin/pip"
CONFIG_FILE="$PROJECT_DIR/config.yaml"
REQUIREMENTS_FILE="$PROJECT_DIR/requirements_service.txt"

# 1. 安装系统依赖
sudo apt update
sudo apt install -y python3 python3-venv python3-pip

# 2. 创建虚拟环境（如果不存在）
if [ ! -d "$VENV_DIR" ]; then
    echo "[INFO] 创建虚拟环境..."
    python3 -m venv "$VENV_DIR"
fi

# 3. 激活虚拟环境并安装依赖
source "$VENV_DIR/bin/activate"
$PYTHON_BIN -m pip install --upgrade pip
$PIP_BIN install --break-system-packages -r "$REQUIREMENTS_FILE"

echo "[INFO] Python依赖安装完成"

# 4. 自动生成 systemd 服务文件
sudo tee /etc/systemd/system/$SERVICE_NAME > /dev/null <<EOF
[Unit]
Description=Power Monitor Service
After=network.target
Wants=network.target

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$PYTHON_BIN $PROJECT_DIR/power_monitor_service.py --config $CONFIG_FILE
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo "[INFO] systemd 服务文件已生成: /etc/systemd/system/$SERVICE_NAME"

# 5. 重新加载 systemd 并启动服务
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
sudo systemctl restart $SERVICE_NAME

echo "[INFO] 服务已启动，可用如下命令查看状态："
echo "sudo systemctl status $SERVICE_NAME"
echo "sudo journalctl -u $SERVICE_NAME -f"
echo "[INFO] 自动化部署完成！" 