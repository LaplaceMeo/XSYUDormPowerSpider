#!/bin/bash

# 电费监控服务安装脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查是否为root用户
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "此脚本需要root权限运行"
        exit 1
    fi
}

# 检查系统要求
check_requirements() {
    print_info "检查系统要求..."
    
    # 检查Python3
    if ! command -v python3 &> /dev/null; then
        print_error "Python3 未安装，请先安装Python3"
        exit 1
    fi
    
    # 检查pip3
    if ! command -v pip3 &> /dev/null; then
        print_error "pip3 未安装，请先安装pip3"
        exit 1
    fi
    
    print_info "系统要求检查通过"
}

# 安装Python依赖
install_dependencies() {
    print_info "安装Python依赖..."
    
    pip3 install requests beautifulsoup4 pyyaml schedule
    
    print_info "Python依赖安装完成"
}

# 创建用户和组
create_user() {
    print_info "创建服务用户..."
    
    # 检查用户是否已存在
    if id "power-monitor" &>/dev/null; then
        print_warning "用户 power-monitor 已存在"
    else
        useradd -r -s /bin/false -d /opt/power-monitor power-monitor
        print_info "用户 power-monitor 创建成功"
    fi
}

# 创建目录结构
create_directories() {
    print_info "创建目录结构..."
    
    mkdir -p /opt/power-monitor
    mkdir -p /opt/power-monitor/logs
    mkdir -p /etc/power-monitor
    
    # 设置权限
    chown -R power-monitor:power-monitor /opt/power-monitor
    chmod 755 /opt/power-monitor
    chmod 755 /opt/power-monitor/logs
    
    print_info "目录结构创建完成"
}

# 复制文件
copy_files() {
    print_info "复制服务文件..."
    
    # 复制Python脚本
    cp power_monitor_service.py /opt/power-monitor/
    cp dorm_rooms_2025.csv /opt/power-monitor/
    
    # 复制配置文件
    cp config.yaml /etc/power-monitor/
    
    # 复制服务文件
    cp power-monitor.service /etc/systemd/system/
    
    # 设置权限
    chown power-monitor:power-monitor /opt/power-monitor/power_monitor_service.py
    chown power-monitor:power-monitor /opt/power-monitor/dorm_rooms_2025.csv
    chown power-monitor:power-monitor /etc/power-monitor/config.yaml
    chmod 644 /opt/power-monitor/power_monitor_service.py
    chmod 644 /opt/power-monitor/dorm_rooms_2025.csv
    chmod 644 /etc/power-monitor/config.yaml
    chmod 644 /etc/systemd/system/power-monitor.service
    
    print_info "文件复制完成"
}

# 配置服务
configure_service() {
    print_info "配置systemd服务..."
    
    # 重新加载systemd
    systemctl daemon-reload
    
    # 启用服务
    systemctl enable power-monitor.service
    
    print_info "服务配置完成"
}

# 创建管理脚本
create_management_scripts() {
    print_info "创建管理脚本..."
    
    # 创建启动脚本
    cat > /usr/local/bin/power-monitor-start << 'EOF'
#!/bin/bash
systemctl start power-monitor.service
echo "电费监控服务已启动"
EOF

    # 创建停止脚本
    cat > /usr/local/bin/power-monitor-stop << 'EOF'
#!/bin/bash
systemctl stop power-monitor.service
echo "电费监控服务已停止"
EOF

    # 创建状态查看脚本
    cat > /usr/local/bin/power-monitor-status << 'EOF'
#!/bin/bash
systemctl status power-monitor.service
EOF

    # 创建日志查看脚本
    cat > /usr/local/bin/power-monitor-logs << 'EOF'
#!/bin/bash
journalctl -u power-monitor.service -f
EOF

    # 创建立即执行脚本
    cat > /usr/local/bin/power-monitor-run << 'EOF'
#!/bin/bash
cd /opt/power-monitor
python3 power_monitor_service.py --config /etc/power-monitor/config.yaml --once
EOF

    # 设置执行权限
    chmod +x /usr/local/bin/power-monitor-*
    
    print_info "管理脚本创建完成"
}

# 显示使用说明
show_usage() {
    print_info "安装完成！"
    echo
    echo "使用说明："
    echo "1. 编辑配置文件："
    echo "   sudo nano /etc/power-monitor/config.yaml"
    echo
    echo "2. 启动服务："
    echo "   sudo power-monitor-start"
    echo
    echo "3. 停止服务："
    echo "   sudo power-monitor-stop"
    echo
    echo "4. 查看状态："
    echo "   sudo power-monitor-status"
    echo
    echo "5. 查看日志："
    echo "   sudo power-monitor-logs"
    echo
    echo "6. 立即执行一次监控："
    echo "   sudo power-monitor-run"
    echo
    echo "7. 设置开机自启："
    echo "   sudo systemctl enable power-monitor.service"
    echo
    print_warning "请记得在配置文件中设置正确的SENDKEY和宿舍信息！"
}

# 主安装流程
main() {
    print_info "开始安装电费监控服务..."
    
    check_root
    check_requirements
    install_dependencies
    create_user
    create_directories
    copy_files
    configure_service
    create_management_scripts
    show_usage
    
    print_info "安装完成！"
}

# 卸载函数
uninstall() {
    print_warning "开始卸载电费监控服务..."
    
    # 停止服务
    systemctl stop power-monitor.service 2>/dev/null || true
    
    # 禁用服务
    systemctl disable power-monitor.service 2>/dev/null || true
    
    # 删除服务文件
    rm -f /etc/systemd/system/power-monitor.service
    
    # 删除程序文件
    rm -rf /opt/power-monitor
    
    # 删除配置文件
    rm -rf /etc/power-monitor
    
    # 删除管理脚本
    rm -f /usr/local/bin/power-monitor-*
    
    # 删除用户（可选）
    read -p "是否删除服务用户 power-monitor？(y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        userdel power-monitor 2>/dev/null || true
        print_info "用户已删除"
    fi
    
    # 重新加载systemd
    systemctl daemon-reload
    
    print_info "卸载完成！"
}

# 检查参数
if [[ "$1" == "uninstall" ]]; then
    check_root
    uninstall
else
    main
fi 