# DCBMS 系统架构

## 1. 架构目标

DCBMS 按“界面展示、用例编排、统一数据、协议解析、数据采集、硬件驱动”分层。各层只向下依赖，界面不再解析协议索引，协议层不再操作 Qt 控件。

```text
Presentation / UI
  Dashboard | Realtime | Alarm | Trend | Control | Config | Log
                         |
Application Services
  DeviceService | DashboardService | AlarmService | RecordService | ...
                         |
Data Center
  System -> Stack -> Cluster -> BMU -> Cell
  LatestValue | Quality | Timestamp | Alarm | Statistics
                         |
Protocol / Algorithm
  BMS signal IDs | DBC decoder | Custom BMS protocol | diagnostics
                         |
Data Acquisition
  CAN receiver | TCP | Serial | Modbus | MQTT | Replay source
                         |
Driver
  ZLG | Vector | PCAN | Kvaser | SocketCAN | Virtual CAN
                         |
Hardware
  BAU | BCU | BMU | PCS | UPS | EMS | HV Box | Sensors

Persistence (side boundary)
  SQLite configuration/alarm/event | Parquet history | CSV export | runtime log
```

## 2. 当前已落地的竖向切片

“全簇大屏”是新架构的第一个完整切片：

大屏是应用默认首页，可切换为全屏并使用 `Esc` 退出。其命名轮询序列包含系统状态、SOC、总压、总流、压差、温差、最高温度、最高单体电压 `0x148` 和最低单体电压 `0x14B`。

| 层 | 模块 | 职责 |
| --- | --- | --- |
| Presentation | `presentation/cluster_dashboard_page.py` | 显示全簇对比、热力图、异常簇详情，只消费视图模型 |
| Application | `application/dashboard_service.py` | 调度轮询、归一化工程值、计算簇健康状态 |
| Application | `application/device_service.py` | 装配设备用例，将现有页面与新服务隔离 |
| Data Center | `data_center/runtime_cache.py` | 线程安全的全簇最新值、质量、时间戳、告警和统计 |
| Data Center | `data_center/models.py` | 统一层次模型和数据质量定义 |
| Protocol | `protocol/bms_signal_ids.py` | 大屏使用的协议索引与轮询序列 |
| Acquisition/Protocol adapter | `application/can_service.py` | 现阶段保留 CAN 收发与旧协议能力，后续按用例逐步拆分 |
| Driver | `infrastructure/cxcanfd_driver.py` | 封装 `ControlCANFD.dll` |

## 3. 运行数据流

```text
CANFD frame
  -> CxCanFdDriver.receive
  -> CanApplicationService.poll/decode
  -> DeviceService.poll
  -> DashboardService.ingest_poll_result
  -> RuntimeDataCenter
  -> FleetDashboardView
  -> ClusterDashboardPage
```

大屏页打开时，`MainWindow` 将活动簇设为 `None`，允许全簇响应进入缓存；离开大屏或点击“进入实时监控”后，恢复当前簇的优先轮询。

## 4. 依赖规则

- `presentation/` 只依赖应用服务和不可变视图模型，禁止直接引用驱动 DLL。
- `application/` 负责用例编排，不引用 PyQt6。
- `data_center/` 不依赖 UI、驱动或具体报文格式。
- `protocol/` 保存稳定的协议含义，禁止把魔法索引重复写进页面。
- `infrastructure/` 只封装外部资源、硬件和持久化实现。
- `CANFD/main.py` 是唯一装配根，只创建并连接对象。

## 5. 渐进式迁移策略

`CanApplicationService` 暂时承载历史页面使用的方法。`DeviceService.__getattr__` 是明确的迁移边界，不是新功能扩展点。

新增功能必须先建立显式应用服务；历史功能按 `Alarm -> Record -> Control -> Config -> Replay` 顺序逐步迁移。每次只迁移一条可独立测试的数据链，保持现场 CAN 通信稳定。

## 6. 验证边界

- Data Center：层次、值质量、统计、告警、重建簇。
- Dashboard Service：全簇轮询、工程值换算、超时、预警/告警分类。
- Device Service：轮询结果进入数据中心、运行时配置后重建状态。
- Presentation：异常簇置顶、簇选择、大屏轮询、实时监控跳转。
