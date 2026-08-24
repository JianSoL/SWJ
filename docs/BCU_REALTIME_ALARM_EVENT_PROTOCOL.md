# 大储版 BCU 实时告警事件记录报文协议

版本：V1.0  
适用对象：BCU 固件、BAU/上位机、现场数据记录工具  
适用总线：CAN FD 扩展帧，兼容现有 J1939 风格 29 位 ID

## 1. 设计目标

BCU 需要在告警产生、告警恢复或告警等级变化时，通过报文主动上送一条实时告警事件。上位机收到后追加到事件记录表，并同步维护当前告警表。

本协议解决三件事：

- 记录告警事件流水，而不是只显示当前告警状态。
- 把告警 ID、等级、位置、触发值、阈值、时间和关键电池快照放在同一条报文中。
- 与现有 `BCU1215EFA0` 实时故障信息帧保持兼容。

现有周期告警状态帧 `0x1204EFxx` 仍保留，用于显示当前 128 路告警状态和漏帧校验；实时事件记录使用 `0x1215EFxx`。

## 2. 报文 ID

### 2.1 BCU 实时告警事件帧

| 项目 | 定义 |
|---|---|
| 方向 | BCU -> BAU/上位机 |
| CAN ID | `0x1215EFSA` |
| 示例 | A0 簇：`0x1215EFA0`；A1 簇：`0x1215EFA1` |
| 帧格式 | 扩展帧，CAN FD |
| DLC | 64 |
| 字节序 | 多字节字段均为 little-endian；`event_flag` 按固定字节序匹配 |
| 发送类型 | 事件触发 |
| 建议重发 | 同一事件连续发送 3 次，间隔 20 ms；上位机用 `event_seq` 去重 |

`SA` 为 BCU 地址，范围建议 `0xA0..0xBF`。上位机接收时按 `0x1215EF00 | address` 匹配，并用地址定位簇。

### 2.2 周期告警状态帧

| 项目 | 定义 |
|---|---|
| CAN ID | `0x1204EFSA` |
| 周期 | 1000 ms |
| 内容 | 128 路告警状态，每路 4 bit |
| 用途 | 当前告警状态显示、事件漏帧校验 |

上位机收到实时事件后追加记录；收到周期状态帧后只更新当前状态。若周期状态与事件状态不一致，上位机应追加一条 `状态刷新` 事件并标记来源为周期状态补偿。

## 3. 事件帧格式

### 3.1 总体布局

| 字节偏移 | 长度 | 字段名 | 类型 | 单位/倍率 | 说明 |
|---:|---:|---|---|---|---|
| 0 | 2 | `event_flag` | bytes | - | 事件类型固定字节 |
| 2 | 4 | `alarm_code_raw` | U32 | - | 告警 ID、等级、位置编码 |
| 6 | 2 | `actual_value` | S16 | raw | 告警实际值 |
| 8 | 2 | `threshold_value` | S16 | raw | 告警阈值/触发值 |
| 10 | 4 | `device_time` | U32 | packed | BCU 事件时间 |
| 14 | 2 | `event_seq` | U16 | - | BCU 事件序号，循环递增 |
| 16 | 2 | `active_alarm_count` | U16 | 个 | 当前活动告警数量 |
| 18 | 2 | `run_status` | U16 | - | BCU 运行状态原始值 |
| 20 | 2 | `relay_status` | U16 | bit | 继电器状态 bit0..bit15 |
| 22 | 2 | `total_voltage` | U16 | 0.1 V | 事件发生时总压 |
| 24 | 2 | `total_current` | S16 | 0.1 A | 事件发生时总流 |
| 26 | 2 | `soc` | U16 | 0.1 % | SOC |
| 28 | 2 | `soh` | U16 | 0.1 % | SOH |
| 30 | 2 | `max_cell_voltage` | U16 | mV | 最高单体电压 |
| 32 | 2 | `min_cell_voltage` | U16 | mV | 最低单体电压 |
| 34 | 2 | `max_cell_temperature` | S16 | 0.1 degC | 最高单体温度 |
| 36 | 2 | `min_cell_temperature` | S16 | 0.1 degC | 最低单体温度 |
| 38 | 2 | `max_voltage_position` | U16 | packed | 最高电压位置 |
| 40 | 2 | `min_voltage_position` | U16 | packed | 最低电压位置 |
| 42 | 2 | `max_temperature_position` | U16 | packed | 最高温度位置 |
| 44 | 2 | `min_temperature_position` | U16 | packed | 最低温度位置 |
| 46 | 1 | `alarm_category` | U8 | enum | 告警分类 |
| 47 | 1 | `value_unit` | U8 | enum | `actual_value` 和 `threshold_value` 的单位 |
| 48 | 4 | `bcu_uptime_ms` | U32 | ms | BCU 上电运行时间 |
| 52 | 4 | `duration_ms` | U32 | ms | 恢复事件的持续时间；未知填 `0xFFFFFFFF` |
| 56 | 1 | `protocol_version` | U8 | - | 当前为 `1` |
| 57 | 1 | `event_reason` | U8 | enum | 事件原因 |
| 58 | 2 | `payload_crc16` | U16 | - | 可选，关闭时填 `0x0000` |
| 60 | 4 | `reserved` | U32 | - | 预留，填 `0` |

兼容说明：BCU615 参考代码已经发送前 14 字节：

```text
Byte0..1   event_flag
Byte2..5   alarm_code_raw
Byte6..7   actual_value
Byte8..9   threshold_value
Byte10..13 device_time
```

大储版固件应继续保留这 14 字节含义，并补齐后续快照字段。

### 3.2 `event_flag`

`event_flag` 按报文中的两个字节直接判断，不按 U16 数值判断，避免大小端歧义。

| 字节 0 | 字节 1 | 含义 | 上位机事件类型 |
|---:|---:|---|---|
| `0xFB` | `0xBF` | 告警产生/活动告警上送 | `告警产生` |
| `0xFA` | `0xAF` | 告警恢复/消失 | `告警恢复` |
| `0xFC` | `0xCF` | 告警等级或触发值更新，可选 | `告警更新` |
| 其他 | 其他 | 非法 | 丢弃并记录原始帧 |

现有 DBC 注释里存在 `0xFBBF/0xFAAF/0xBFFB/0xAFFA` 的描述。协议实现以线上的两个字节为准：`FB BF` 表示产生，`FA AF` 表示恢复。

### 3.3 `alarm_code_raw`

`alarm_code_raw` 为 U32，小端，位定义如下：

| bit | 字段 | 说明 |
|---:|---|---|
| 0..6 | `cell_no` | 模组内单体号，0 表示无单体位置；显示时建议 1 基或按固件定义统一 |
| 7..13 | `module_no` | CSU/模组号，0 表示无模组位置 |
| 14..15 | `reserved` | 保留 |
| 16..19 | `device_type` | 设备类型或 BCU 编号；参考固件把簇序号写入此处 |
| 20..23 | `alarm_level` | 告警等级，0 表示无等级，1..5 为告警等级 |
| 24..31 | `alarm_id` | 告警 ID；上位机显示为三位码，例如 `001` |

上位机解码后生成位置文本：

```text
BCU:{device_type:03d}-CSU:{module_no:03d}-Cell:{cell_no:03d}
```

如果某一级位置为 0，可以显示为 `-`。

### 3.4 `device_time`

`device_time` 沿用历史日志时间压缩格式：

| bit | 字段 | 范围 |
|---:|---|---|
| 0..5 | year | `2000 + value` |
| 6..9 | month | 1..12 |
| 10..14 | day | 1..31 |
| 15..19 | hour | 0..23 |
| 20..25 | minute | 0..59 |
| 26..31 | second | 0..59 |

若 BCU RTC 未校准，填 `0`，上位机以接收时间作为事件时间，并把 `device_time_valid=false` 写入记录。

### 3.5 位置编码字段

`max_voltage_position`、`min_voltage_position`、`max_temperature_position`、`min_temperature_position` 使用同一 U16 编码：

| bit | 字段 |
|---:|---|
| 0..4 | BCU 编号 |
| 5..9 | CSU/模组编号 |
| 10..15 | Cell 编号 |

显示格式：

```text
BCU:{bcu:03d}|CSU:{csu:03d}|Cell:{cell:03d}
```

## 4. 枚举定义

### 4.1 `alarm_category`

| 值 | 分类 |
|---:|---|
| 0 | 未分类 |
| 1 | 电压类 |
| 2 | 温度类 |
| 3 | 电流类 |
| 4 | 绝缘类 |
| 5 | SOC/SOH 类 |
| 6 | 通讯类 |
| 7 | 继电器/高压回路类 |
| 8 | 传感器类 |
| 9 | 功能安全类 |
| 10 | 参数/配置类 |
| 255 | 其他 |

### 4.2 `value_unit`

| 值 | 单位/倍率 | 用途 |
|---:|---|---|
| 0 | raw | 无统一单位 |
| 1 | mV | 单体电压、压差 |
| 2 | 0.1 V | 总压、模组电压 |
| 3 | 0.1 A | 电流 |
| 4 | 0.1 degC | 温度 |
| 5 | 0.1 % | SOC/SOH |
| 6 | kOhm | 绝缘阻值 |
| 7 | ms | 时间 |
| 255 | custom | 上位机按告警 ID 自定义解析 |

### 4.3 `event_reason`

| 值 | 含义 |
|---:|---|
| 0 | 未指定 |
| 1 | 实时状态变化 |
| 2 | 上电后活动告警补发 |
| 3 | 上位机请求活动告警快照 |
| 4 | 周期状态校验补偿 |
| 5 | 告警等级变化 |

## 5. 上位机记录字段

上位机收到事件帧后，应生成一条不可变事件记录。推荐 CSV/数据库字段如下：

| 字段名 | 来源 | 说明 |
|---|---|---|
| `record_id` | 上位机生成 | `{receive_time}_{cluster_address}_{event_seq}_{alarm_code}` |
| `receive_time` | 上位机 | 上位机收到报文的时间 |
| `device_time` | 报文 Byte10..13 | BCU 事件时间 |
| `device_time_valid` | 上位机解码 | RTC 是否有效 |
| `cluster_index` | 配置/地址映射 | 簇编号 |
| `cluster_address` | CAN ID SA | BCU 地址 |
| `event_seq` | Byte14..15 | 事件序号 |
| `event_type` | `event_flag` | 告警产生/恢复/更新 |
| `event_reason` | Byte57 | 事件原因 |
| `alarm_id` | `alarm_code_raw` bit24..31 | 告警 ID |
| `alarm_code` | 上位机格式化 | 三位码，例如 `001` |
| `alarm_name` | 配置映射 | 来自 `Alarm_name_key` 或告警参数表 |
| `alarm_level` | `alarm_code_raw` bit20..23 | 告警等级 |
| `alarm_status` | `event_flag` | active/cleared/updated |
| `alarm_category` | Byte46 | 告警分类 |
| `location_text` | `alarm_code_raw` | 位置文本 |
| `bcu_no` | `alarm_code_raw` bit16..19 | BCU/设备编号 |
| `module_no` | `alarm_code_raw` bit7..13 | CSU/模组号 |
| `cell_no` | `alarm_code_raw` bit0..6 | 单体号 |
| `actual_value_raw` | Byte6..7 | 原始实际值 |
| `threshold_value_raw` | Byte8..9 | 原始阈值 |
| `value_unit` | Byte47 | 单位枚举 |
| `actual_value_text` | 上位机格式化 | 带单位实际值 |
| `threshold_value_text` | 上位机格式化 | 带单位阈值 |
| `active_alarm_count` | Byte16..17 | 当前活动告警数量 |
| `run_status` | Byte18..19 | BCU 运行状态 |
| `relay_status` | Byte20..21 | 继电器状态 |
| `total_voltage` | Byte22..23 | 单位 V |
| `total_current` | Byte24..25 | 单位 A |
| `soc` | Byte26..27 | 单位 % |
| `soh` | Byte28..29 | 单位 % |
| `max_cell_voltage` | Byte30..31 | mV |
| `min_cell_voltage` | Byte32..33 | mV |
| `max_cell_temperature` | Byte34..35 | degC |
| `min_cell_temperature` | Byte36..37 | degC |
| `max_voltage_position` | Byte38..39 | 位置文本 |
| `min_voltage_position` | Byte40..41 | 位置文本 |
| `max_temperature_position` | Byte42..43 | 位置文本 |
| `min_temperature_position` | Byte44..45 | 位置文本 |
| `bcu_uptime_ms` | Byte48..51 | BCU 上电运行时间 |
| `duration_ms` | Byte52..55 | 恢复事件持续时间 |
| `source_frame_id` | CAN ID | 原始 CAN ID |
| `raw_payload` | CAN data | 64 字节 HEX |
| `confirm_status` | 上位机 | 未确认/已确认 |
| `confirm_user` | 上位机 | 确认人，可空 |
| `confirm_time` | 上位机 | 确认时间，可空 |
| `remark` | 上位机 | 备注 |

推荐 CSV 表头：

```csv
记录ID,接收时间,设备时间,设备时间有效,簇编号,簇地址,事件序号,事件类型,事件原因,告警ID,告警码,告警名称,告警等级,告警状态,告警分类,位置,BCU编号,模组编号,单体编号,实际值Raw,阈值Raw,单位,实际值,阈值,活动告警数量,运行状态,继电器状态,总压[V],总流[A],SOC[%],SOH[%],最高单体电压[mV],最低单体电压[mV],最高单体温度[degC],最低单体温度[degC],最高电压位置,最低电压位置,最高温度位置,最低温度位置,BCU运行时间[ms],持续时间[ms],来源帧ID,原始报文,确认状态,确认人,确认时间,备注
```

## 6. 发送策略

### 6.1 告警产生

当某告警从无效变为有效，或从低等级变为更高等级时，BCU 发送 `FB BF` 事件帧。

建议：

- `event_reason=1`，实时状态变化。
- `duration_ms=0xFFFFFFFF`。
- 若等级变化不希望拆成恢复+产生，可发送 `FC CF` 更新帧，`event_reason=5`。

### 6.2 告警恢复

当某告警从有效变为无效时，BCU 发送 `FA AF` 事件帧。

建议：

- `duration_ms` 填告警持续时间。
- `alarm_level` 填恢复前最高等级。
- `actual_value` 填恢复时实际值。

### 6.3 活动告警补发

BCU 上电、地址完成、通信恢复或上位机请求快照时，应把当前活动告警逐条按 `FB BF` 发送。

建议：

- `event_reason=2`：上电后补发。
- `event_reason=3`：上位机请求快照。
- 上位机记录为 `状态刷新` 或 `活动告警补发`，避免误判为新的产生事件。

### 6.4 去重规则

上位机用以下组合去重：

```text
cluster_address + event_seq + event_flag + alarm_code_raw
```

若固件暂未实现 `event_seq`，上位机可用以下组合在 1 秒窗口内去重：

```text
cluster_address + event_flag + alarm_code_raw + device_time
```

## 7. 异常和无效值

| 类型 | 无效值 |
|---|---|
| U8 | `0xFF` |
| U16 | `0xFFFF` |
| S16 | `0x7FFF` |
| U32 | `0xFFFFFFFF` |
| 时间 | `0x00000000` |

上位机遇到无效值时，显示为空或 `--`，但原始值必须写入 `raw_payload`。

## 8. 与历史日志的关系

实时事件帧用于“在线过程记录”，历史日志诊断命令用于“离线补齐和追溯”。

| 功能 | 协议 |
|---|---|
| 实时告警事件 | `0x1215EFSA` 主动上送 |
| 当前告警状态 | `0x1204EFSA` 周期上送 |
| 历史日志数量 | 诊断命令 `0x86`，响应 `0x87` |
| 历史日志单条 | 诊断命令 `0x86`，8 包响应 |
| 清空历史日志 | 控制命令，要求工厂模式 |

上位机启动后建议流程：

1. 监听 `0x1215EFSA`，实时追加事件记录。
2. 周期读取 `0x1204EFSA`，刷新当前告警状态。
3. 如发现状态缺口或用户要求追溯，再用 `0x86/0x87` 读取历史日志。

## 9. DBC 修订建议

当前 `DCFDV1.3.dbc` 中 `BCU1215EFA0` 已存在，但字段定义不足以表达大储版完整记录：

```text
BO_ 2450911136 BCU1215EFA0: 64 BCU
 SG_ ALARM_TIME : 72|32@1- ...
 SG_ ALARM_AlmLvValue : 56|16@1- ...
 SG_ ALARM_RealValue : 40|16@1- ...
 SG_ ALARM_INFO1 : 8|32@1+ ...
 SG_ ALARM_ADD_REMOVE_FLAG : 0|1@1+ ...
```

建议后续 DBC 同步修订：

- `ALARM_ADD_REMOVE_FLAG` 从 1 bit 改为 16 bit 或拆成 `ALARM_FLAG_BYTE0`、`ALARM_FLAG_BYTE1`。
- `ALARM_INFO1` 起始位调整为 Byte2，即 bit16。
- 增加本协议 Byte14..63 的扩展字段。
- 为 `0x1215EFxx` 增加地址别名解析，上位机用 A0 模板兼容 A1..BF。

## 10. 示例

告警产生示例，A1 簇，告警 ID 32，三级告警，CSU 2，Cell 4：

```text
CAN ID: 0x1215EFA1
DLC:    64
Data:
FB BF 04 01 30 20 34 08 D0 07 80 15 62 68
2A 00 03 00 02 00 09 00 54 0C 00 00 46 03 E8 03
7C 0D 11 0D 87 01 10 01 24 08 25 08 24 08 25 08
01 01 90 5F 01 00 FF FF FF FF 01 01 00 00 00 00
```

解码要点：

- `FB BF`：告警产生。
- `alarm_code_raw=0x20300104`：告警 ID 32，等级 3，设备/BCU 0，CSU 2，Cell 4。
- `actual_value=2100`，`threshold_value=2000`。
- `event_seq=42`。
- `total_voltage=315.6 V`，`soc=83.8 %`。

