# DCBMS 命名与代码规范

## 1. 命名

| 对象 | 规则 | 示例 |
| --- | --- | --- |
| Python 文件/目录 | `snake_case` | `dashboard_service.py`, `data_center/` |
| 类、数据类、枚举 | `PascalCase` | `RuntimeDataCenter`, `ClusterHealth` |
| 函数、方法、变量 | `snake_case` | `refresh_cluster`, `last_seen_at` |
| 常量、固定映射 | `UPPER_SNAKE_CASE` | `DASHBOARD_POLL_SEQUENCE` |
| Qt signal | 过去式或动作结果 | `cluster_activated` |
| 布尔值 | `is_` / `has_` / `can_` / `should_` | `is_open`, `has_alarm` |
| 物理量 | 名称或视图模型中明确单位 | `communication_timeout_s`, `system_voltage` + `V` |

禁止使用 `data1`、`tmp`、`obj`、`handle2` 等无业务含义的名称。协议索引必须在 `protocol/` 命名，页面中不得新增裸的十六进制魔法数。

## 2. 模块边界

- 每个页面模块只负责布局、交互和显示格式。
- 阈值、单位换算、轮询策略放在应用服务，不散落到 Qt 控件事件中。
- 运行态数据优先使用 dataclass；跨层传递的视图模型使用 `frozen=True`。
- 底层异常在应用层转换为明确的用例结果，UI 只负责告知用户。
- 新页面不得继续扩展 `DeviceService.__getattr__` 兼容路径。

## 3. 方法与可读性

- 公开方法名表达业务动作，例如 `refresh_dashboard()`，不使用 `do_it()`。
- 避免重复定义同名方法；保留的历史实现必须以 `_legacy_` 命名并标注迁移原因。
- 复杂条件先提取为具名布尔变量，不在 UI 刷新函数中堆叠三元表达式。
- 注释解释“为什么”和边界约束，不复述代码字面行为。
- 公共类和非直观的迁移边界需要 docstring。

## 4. 测试规则

- 修改协议换算：必须测试正数、负数、边界值和无响应。
- 修改数据中心：必须测试值、质量、时间戳和统计。
- 修改应用服务：必须测试用例输入/输出，不依赖实机 CAN 设备。
- 修改页面交互：使用 `QT_QPA_PLATFORM=offscreen` 验证选择、切页和主操作。
- 提交前运行全量 `unittest` 和 `git diff --check`。

## 5. 历史文件例外

`UI/T*.py`、`SIGNAL.py` 等是已有 Qt 生成代码或历史入口。本次不批量改名，避免打断导入、PyInstaller 和现场发布路径。新增代码全部遵守本规范，历史文件只在其功能被独立测试覆盖后再逐个迁移。

## 6. 合并检查清单

- [ ] 文件、类、方法、常量命名符合规范。
- [ ] UI 没有新增协议解析或魔法索引。
- [ ] 跨层数据契约有类型和单位。
- [ ] 新增用例有自动化测试。
- [ ] 发布资源和启动入口未被破坏。

