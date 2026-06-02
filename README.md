# DCBMS

DCBMS 是一个基于 `PyQt6` 的 CANFD 上位机程序，用于连接 CANFD 适配器，发送 BCU 请求报文，并展示周期报文、均衡状态、告警状态、单体电压、单体温度等数据。

当前业务入口为 `CANFD/main.py`。根目录下的 `main.py` 只是示例脚本，不参与实际运行。

## 功能概览

- 连接 `USBCAN2` CANFD 设备
- 按簇查看请求响应数据
- 按 DBC 解析周期 CANFD 报文
- 展示单体电压、单体温度、均衡状态、告警状态、极柱温度
- 支持运行时切换 `device_index` 和 `channel_index`
- 支持会话日志落盘

## 目录结构

```text
DCBMS/
├─ CANFD/
│  ├─ application/      # 应用服务层：请求协议、轮询、日志调度
│  ├─ domain/           # 领域层：DBC 解析、信号定义、模型
│  ├─ infrastructure/   # 基础设施层：ControlCANFD.dll 封装
│  ├─ presentation/     # UI 层：主窗口和页面刷新
│  ├─ tests/            # 单元测试和硬件冒烟脚本
│  ├─ UI/               # Qt 生成界面和部件
│  ├─ SINGLE/BCU.xlsx   # 旧协议信号定义
│  ├─ conf.yaml         # 运行配置
│  └─ main.py           # 实际程序入口
├─ ControlCANFD.dll     # CANFD 驱动 DLL
├─ DCFDV1.3.dbc         # 周期报文 DBC
├─ DCBMS.spec           # PyInstaller 打包配置
└─ build_exe.ps1        # 一键打包脚本
```

## 运行依赖

硬件和文件依赖：

- 中新创 / 同类 `ControlCANFD.dll` 对应的 CANFD 适配器
- `ControlCANFD.dll`
- `DCFDV1.3.dbc`
- `CANFD/conf.yaml`
- `CANFD/SINGLE/BCU.xlsx`

Python 依赖：

- `Python 3.8`
- `PyQt6`
- `PyYAML`
- `pandas`
- `openpyxl`
- `PyInstaller`（仅打包时需要）

示例安装：

```powershell
pip install PyQt6 PyYAML pandas openpyxl pyinstaller
```

## 运行源码

建议从 `CANFD` 目录启动：

```powershell
cd CANFD
python main.py
```

如果本机没有连接 CANFD 设备，程序启动时会尝试打开总线，并弹出连接失败提示框。这是当前设计行为，不是打包故障。

## 配置说明

主配置文件为 `CANFD/conf.yaml`，默认使用 `Test_4_10` 配置项。关键字段包括：

- `DEVICE_INDEX`：设备号
- `CHANNEL_INDEX`：通道号
- `BCU_NUM`：簇数量
- `LECU_NUM`：每簇采集单元数量
- `CELL_NUM`：单体电压数量
- `CELL_Tem_NUM`：单体温度数量
- `SAVE_LOG`：是否保存日志
- `ADDRESLIST`：簇地址列表

UI 顶部也可以在运行时修改 `device_index` 和 `channel_index`，点击“应用并重连”后生效。

## 测试

自动化测试：

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python -m unittest discover -s CANFD\tests -p "test_*.py" -v
```

手动硬件冒烟：

```powershell
cd CANFD
python tests\manual_hardware_smoke.py
```

自动化测试覆盖：

- 程序装配和启动路径
- DLL 驱动封装
- 请求/响应协议解析
- DBC 周期报文解析
- UI 刷新与关闭清理
- 会话日志写入

## 打包 EXE

仓库已经提供了 `PyInstaller` 配置和一键打包脚本。

执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```

默认会使用：

```text
C:\Users\ch\.conda\envs\QT\python.exe
```

如果该解释器不存在，脚本会回退到当前环境的 `python`。

也可以手动指定：

```powershell
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1 -PythonExe "D:\path\to\python.exe"
```

打包产物：

- `dist\DCBMS\DCBMS.exe`

发布时请带上整个 `dist\DCBMS` 目录，不要只拷贝单个 `exe`，因为运行还依赖 `_internal` 目录中的 Qt、Python 运行库、DLL 和资源文件。

## 打包包含内容

`DCBMS.spec` 已显式包含以下运行资源：

- `ControlCANFD.dll`
- `DCFDV1.3.dbc`
- `CANFD/conf.yaml`
- `CANFD/SINGLE/BCU.xlsx`
- `CANFD/alarm.wav`
- `CANFD/1.ico`

另外，`CANFD/UI/T31.py` 已处理 PyInstaller 资源路径，打包后仍可正确查找报警音频。

## 分层说明

项目采用三层结构：

- `infrastructure/cxcanfd_driver.py`
  - 对 `ControlCANFD.dll` 做 `ctypes` 封装
- `application/can_service.py`
  - 负责请求发送、接收轮询、协议解析、日志调度
- `presentation/main_window.py`
  - 负责 Qt 定时器、页面刷新和用户交互

依赖方向为：

```text
presentation -> application -> domain/infrastructure
```

`application` 不依赖 Qt，`infrastructure` 不依赖 UI。

## 常见问题

### 1. 双击 EXE 后提示打开设备失败

优先检查：

- 适配器是否已连接
- 驱动是否正常安装
- 设备是否被其他程序占用
- `device_index` 和 `channel_index` 是否正确

### 2. 打包后程序能启动但没有数据

优先检查：

- `conf.yaml` 中簇地址配置是否正确
- `DCFDV1.3.dbc` 是否与当前整车/电池协议版本一致
- `BCU.xlsx` 是否与旧协议信号定义一致

### 3. 只复制了 `DCBMS.exe`，运行报缺文件

这是错误的发布方式。请分发整个 `dist\DCBMS` 目录。
