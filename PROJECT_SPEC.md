# SheetFlow v0.1.0 项目规格

## 背景与目标用户

SheetFlow 用于替代行政、财务、运营、电商人员和自由职业者重复执行的 Excel/CSV 合并与清洗工作。首版提供无需编程、离线可用、能保存并重放流程的 Windows 工具。

## 核心功能

- 读取 CSV/XLSX，支持目录输入、工作表、表头行、CSV 编码与分隔符。
- 合并文件并可增加来源列。
- `drop_empty`、`trim_text`、`rename_columns`、`drop_columns`、`reorder_columns`、`drop_duplicates`、`filter`、`sort`、`convert_type`、`fill_null`、`group_summary`、`split_by`。
- 导出 CSV/XLSX，Excel 自动设置表头、筛选、冻结窗格和列宽。
- YAML 工作流、CLI 和中文 GUI 共用同一处理引擎。

## 技术栈与结构

Python 3.11+；pandas、openpyxl、Pydantic、PyYAML、Typer、PySide6、pytest、ruff、mypy、PyInstaller。源码按配置、读取、操作、导出、任务服务、CLI、GUI 分层，界面不得包含重复的数据处理实现。

## CLI 与 GUI

CLI 提供 `version`、`inspect`、`validate`、`merge`、`run`、`gui`。GUI 提供文件/目录选择、最多 100 行预览、步骤新增/删除/排序/JSON 参数编辑、工作流保存与加载、输出选择、进度和安全取消。

## 异常与安全

处理不存在、无权限、损坏、编码失败、缺列、类型转换失败、配置错误、输出已存在和取消。默认不覆盖、不修改输入、不联网、不记录表格内容。正式输出必须经过同目录临时文件原子替换。

## 测试与打包

核心业务覆盖率目标不低于 85%，测试正常链路、中文路径、损坏文件、部分失败、边界值、覆盖保护和取消。Windows 使用 PyInstaller 生成无需 Python 的便携目录版，并提供 SHA-256。

## 开源与商业边界

Apache-2.0。基础本地读写、数据处理、工作流、CLI 和 GUI 永久作为可独立工作的开源核心；团队协作、云服务、企业连接器、集中部署和支持服务可商业化。

## 交付与验收

交付源码、文档、示例、测试、CI、Windows 包和校验值。只有 CLI/GUI 能处理中文 CSV/XLSX、工作流可往返复用、失败不破坏输入和输出、测试通过、干净 Windows 环境可运行时才算完成。

## 开发顺序

项目骨架与模型

↓

读取与检查

↓

数据操作

↓

安全导出与任务编排

↓

CLI

↓

GUI

↓

测试、文档、Windows 打包与发布

