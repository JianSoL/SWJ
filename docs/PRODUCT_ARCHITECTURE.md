# DCBMS 产品化架构说明

## 发布目标

DCBMS 按标准产品上位机交付时，需要满足三个边界清晰：

- 运行边界清晰：入口、配置、DBC、YAML 信号表、主题、图标、声音、日志目录由统一运行时上下文解析。
- 分层边界清晰：UI 只负责交互和展示，应用层负责 CANFD 协议和轮询，基础设施层负责 DLL 调用。
- 交付边界清晰：发布前检查脚本能验证必需资源、自动化测试和 PyInstaller 打包入口。

## 运行时上下文

新增 `CANFD/application/runtime.py` 作为产品运行时边界：

- 源码运行时，资源来自 `CANFD/` 和仓库根目录。
- PyInstaller 运行时，资源优先来自 `sys._MEIPASS`。
- 日志默认写入源码模式的 `CANFD/log/` 或 EXE 所在目录的 `log/`。
- `DCBMS_PROFILE` 可切换 `conf.yaml` 中的配置 profile。
- `DCBMS_LOG_DIR` 可覆盖日志输出目录。

主程序入口 `CANFD/main.py` 只负责装配依赖：

```text
runtime paths -> config -> catalog/dbc/log -> driver -> service -> MainWindow
```

## 分层约束

当前依赖方向：

```text
presentation -> application -> domain
                         \-> infrastructure
```

约束如下：

- `presentation/` 可以依赖 Qt 和应用服务，但不要直接调用 `ControlCANFD.dll`。
- `application/` 不依赖 Qt，负责请求/响应、DBC 解析调度、日志调度和业务状态。
- `domain/` 放数据模型、DBC 运行时、信号目录等纯业务结构。
- `infrastructure/` 封装硬件驱动、DLL 结构体和底层收发。
- 根目录 `main.py` 只是产品启动器，不放业务逻辑。

## 发布流程

发布前先运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\release_check.ps1
```

完整打包：

```powershell
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```

发布检查覆盖：

- 必需资源文件存在性。
- 根入口和 CANFD 入口可编译。
- 全量单元测试。
- 可选 PyInstaller 构建。

## 发布包内容

发布时分发整个 `dist/DCBMS/` 目录，不单独拷贝 `DCBMS.exe`。

必须包含：

- `DCBMS.exe`
- `_internal/` 运行时依赖
- `ControlCANFD.dll`
- `DCFDV1.3.dbc`
- `conf.yaml`
- `SINGLE/BCU.yaml`
- `UI/release_theme.qss`
- `1.ico`
- `alarm.wav`

## 后续演进建议

- 把 `application/can_service.py` 中的告警参数、历史日志、均衡控制协议逐步拆成独立 use case。
- 给硬件驱动定义 Protocol 接口，便于接入仿真驱动、回放驱动和自动化验收。
- 把产品版本写入 CI 或发布脚本生成的 manifest，避免手动维护多处版本号。
