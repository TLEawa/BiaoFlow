# SheetFlow

[![最新版本](https://img.shields.io/github/v/release/TLEawa/SheetFlow?label=%E6%9C%80%E6%96%B0%E7%89%88%E6%9C%AC&color=blue)](https://github.com/TLEawa/SheetFlow/releases/latest)
[![自动测试](https://github.com/TLEawa/SheetFlow/actions/workflows/ci.yml/badge.svg)](https://github.com/TLEawa/SheetFlow/actions/workflows/ci.yml)
[![许可证](https://img.shields.io/github/license/TLEawa/SheetFlow)](LICENSE)

SheetFlow 是一个离线优先的电商订单批处理工具。它把淘宝、拼多多、抖店等平台导出的多份订单表，整理成可直接发货、对账和统计的结果表。

> **当前开源版本：v0.3.0。** 文件默认只在本机处理，不上传、不包含遥测。

## 下载 Windows 版

[下载 SheetFlow v0.3.0 Windows 便携版](https://github.com/TLEawa/SheetFlow/releases/download/v0.3.0/SheetFlow-0.3.0-windows.zip)

下载后解压，运行 `gui\SheetFlow.exe`，无需安装 Python。旧版 `v0.1.0` 仅作为历史版本保留。

## 先解决一个具体问题：订单表太多

把一周的订单文件拖进来，选择“电商订单整理”，SheetFlow 会按订单号去重、清理空白、保留来源，并输出一份合并结果。需要发货时，还可以按省份或店铺拆分文件。

## 功能

- CSV/XLSX 单文件、批量文件和目录输入
- CSV 常见中文编码与分隔符自动识别
- 合并、来源列、去空行、清理空格、列操作、去重、筛选、排序和类型转换
- 分组统计及按列值拆分文件
- CSV/XLSX 安全导出，默认禁止覆盖
- 可保存、校验并复用的 YAML 工作流
- 中文桌面 GUI 与统一的 CLI 核心
- 用中文描述自动生成可编辑的处理步骤（本地规则解析）
- 电商订单、客户名单、考勤表和通用清洗模板
- 执行前真实预览，显示处理前后的行数与列数变化

## 5 分钟快速开始

开发环境需要 Python 3.11 或更高版本。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[gui]"
.\.venv\Scripts\sheetflow.exe --help
.\.venv\Scripts\sheetflow.exe run examples\workflows\basic.yaml
```

启动界面：

```powershell
.\.venv\Scripts\sheetflow-gui.exe
```

Windows 发行包用户可直接运行 `SheetFlow.exe`，无需安装 Python。

## 用一句话创建流程

GUI 中先添加文件，再输入：

> 合并文件并保留来源，按手机号去重，再按城市拆分

点击“从描述生成步骤”后，SheetFlow 会依据实际列名生成可编辑步骤。
未能确定的列会明确提示，不会猜测。点击“预览前 100 行”可以在写文件前
查看真实处理结果。

命令行也可以生成工作流：

```powershell
sheetflow suggest orders.csv "按订单号去重，再按城市拆分" --save workflow.yaml
```

> 这一版的“智能创建”是可预期、可复核的本地规则解析器，不是云端大模型，
> 不需要 API Key，也不会上传表格。

## CLI 示例

```powershell
sheetflow inspect input.xlsx
sheetflow validate workflow.yaml
sheetflow merge a.csv b.xlsx --output result.xlsx --add-source
sheetflow suggest input.xlsx "删除空行，按手机号去重" --save workflow.yaml
sheetflow run workflow.yaml
sheetflow gui
```

## 工作流

```yaml
version: 1
input:
  paths: [../sample_input]
  on_error: continue
operations:
  - type: merge
    add_source_column: true
  - type: trim_text
  - type: drop_duplicates
    columns: [订单号]
  - type: group_summary
    group_by: [地区]
    aggregations:
      销售额: sum
output:
  path: ../../work/result.xlsx
  overwrite: false
```

配置中的相对路径以 YAML 文件所在目录为准。支持的操作及参数见 [项目规格](PROJECT_SPEC.md)。

## 数据安全与已知限制

- SheetFlow 不修改输入文件，输出先写临时文件，成功后再放入目标路径。
- 默认不联网；日志不会记录完整表格内容。
- 当前支持 `.csv` 和 `.xlsx`，暂不支持旧式 `.xls`、密码文件、VBA、图表编辑和云端协作。
- 大文件受本机可用内存限制；GUI 预览最多显示 100 行。
- 自然语言功能当前覆盖常见合并、清洗、去重、排序、拆分和汇总表述；
  生成后必须先预览，再执行正式导出。
- Excel 公式按 openpyxl/pandas 的读取结果处理，不执行宏。

## 开发、测试与构建

```powershell
python -m pip install -e ".[gui,dev,build]"
pytest
ruff check .
mypy src
pyinstaller packaging\SheetFlow.spec --noconfirm --clean
```

问题与功能建议请使用 GitHub Issues。安全问题请不要公开附带真实数据，可先建立不含敏感信息的最小复现。

## 开源与商业服务

核心本地处理、CLI、基础 GUI 和工作流采用 Apache-2.0 开源。团队协作、云端定时任务、企业连接器、集中部署、培训和定制开发可作为独立商业服务，但不会故意破坏开源版本的基础可用性。

贡献前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。变更记录见 [CHANGELOG.md](CHANGELOG.md)。

## 许可证

Apache License 2.0，见 [LICENSE](LICENSE)。
