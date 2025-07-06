# XSYUDormPowerSpider

西安石油大学宿舍电量查询爬虫工具，通过自动化爬取宿舍编号对应电量数据，解决手动查询繁琐问题，实现电量信息快速获取与可视化监测。

## 项目背景

西安石油大学同学需频繁登录小程序查询宿舍剩余电量，手动操作流程繁琐。本项目通过爬虫技术自动化获取电量数据，结合数据可视化与便捷功能，大幅提升查询效率，减少操作成本。

## 核心功能

### 1. 宿舍电量快速查询
- 输入宿舍编号即可获取**当天剩余电量**

### 2. 耗电数据可视化监测
- 实时记录每天耗电数据
- 自动生成**耗电趋势折线图**（支持日/周/月维度）
- 数据存储至本地数据库，支持历史记录回溯

### 3. 电费充值快捷入口
- 一键跳转至学校官方充值界面

## 技术架构

### 爬虫模块
- 基于Python的`requests`与`BeautifulSoup`实现网页解析


### 硬件交互模块
- 主控芯片：ESP32
- 编程语言：MicroPython
- 显示设备：OLED屏幕
- 通信方式：Wi-Fi

## 项目作者

### 机械师
- 职责：爬虫核心开发，逻辑优化、数据库设计、Windows桌面程序开发（exe封装）

### LaplaceHe
- 职责：爬虫初始逻辑、ESP32单片机程序、Android APP框架搭建

## 使用指南

### 1. 环境部署# 克隆仓库
git clone https://github.com/yourusername/XSYUDormPowerSpider.git
cd XSYUDormPowerSpider

# 安装Python依赖
pip install -r requirements.txt


### OLED屏幕电量显示效果
![ESP32实时显示宿舍电量](XSYUDormPowerSpider/img/展示1.png)


## 联系方式
如有问题或合作需求，可通过以下方式联系：
- 机械师 QQ：2126319400
- LaplaceHe QQ：2590979868

## 许可证
[MIT License](LICENSE)
    