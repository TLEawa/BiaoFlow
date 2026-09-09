# SheetFlow

SheetFlow 是一个离线优先的 Excel/CSV 自动化工具，面向需要重复合并、清洗、筛选和汇总表格的个人与小团队。

> 当前版本：0.1.0。文件默认只在本机处理，不上传、不包含遥测。

## 功能

- CSV/XLSX 单文件、批量文件和目录输入
- CSV 常见中文编码与分隔符自动识别
- 合并、来源列、去空行、清理空格、列操作、去重、筛选、排序和类型转换
- 分组统计及按列值拆分文件
- CSV/XLSX 安全导出，默认禁止覆盖
- 可保存、校验并复用的 YAML 工作流
- 中文桌面 GUI 与统一的 CLI 核心

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

## CLI 示例

```powershell
sheetflow inspect input.xlsx
sheetflow validate workflow.yaml
sheetflow merge a.csv b.xlsx --output result.xlsx --add-source
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

