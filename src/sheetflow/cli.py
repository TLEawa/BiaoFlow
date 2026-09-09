from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from sheetflow import __version__
from sheetflow.config import (
    InputConfig,
    OperationConfig,
    OutputConfig,
    WorkflowConfig,
    load_workflow,
)
from sheetflow.exceptions import SheetFlowError
from sheetflow.readers import inspect_table
from sheetflow.service import run_workflow

app = typer.Typer(help="SheetFlow：离线 Excel/CSV 自动化工具", no_args_is_help=True)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version_option: Annotated[
        bool,
        typer.Option("--version", callback=_version_callback, is_eager=True, help="显示版本"),
    ] = False,
) -> None:
    """SheetFlow 命令行入口。"""


def _fail(exc: Exception) -> None:
    typer.echo(f"错误：{exc}", err=True)
    raise typer.Exit(code=1)


@app.command()
def version() -> None:
    """显示版本。"""
    typer.echo(__version__)


@app.command("validate")
def validate_config(workflow: Annotated[Path, typer.Argument(exists=True, dir_okay=False)]) -> None:
    """验证 YAML 工作流。"""
    try:
        load_workflow(workflow)
        typer.echo("配置有效")
    except SheetFlowError as exc:
        _fail(exc)


@app.command()
def inspect(
    source: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    sheet: Annotated[str | None, typer.Option(help="工作表名称")] = None,
) -> None:
    """检查文件结构并预览前五行。"""
    try:
        info = inspect_table(source, sheet=sheet)
        typer.echo(json.dumps(info, ensure_ascii=False, indent=2, default=str))
    except SheetFlowError as exc:
        _fail(exc)


@app.command()
def run(workflow: Annotated[Path, typer.Argument(exists=True, dir_okay=False)]) -> None:
    """执行 YAML 工作流。"""
    try:
        report = run_workflow(
            load_workflow(workflow), progress=lambda _, message: typer.echo(message)
        )
        for output in report.output_paths:
            typer.echo(f"已输出：{output}")
        typer.echo(
            f"输入 {report.input_count}，成功 {report.success_count}，"
            f"失败 {report.skipped_count}，结果 {report.rows} 行"
        )
        if report.partial_failure:
            raise typer.Exit(code=2)
    except SheetFlowError as exc:
        _fail(exc)


@app.command()
def merge(
    inputs: Annotated[list[Path], typer.Argument(help="输入 CSV/XLSX 文件")],
    output: Annotated[Path, typer.Option("--output", "-o", help="输出文件")],
    overwrite: Annotated[bool, typer.Option(help="允许覆盖输出")] = False,
    add_source: Annotated[bool, typer.Option(help="添加来源文件列")] = False,
) -> None:
    """快速合并多个表格。"""
    config = WorkflowConfig(
        version=1,
        input=InputConfig(paths=[str(path) for path in inputs]),
        operations=[
            OperationConfig.model_validate({"type": "merge", "add_source_column": add_source})
        ],
        output=OutputConfig(path=str(output), overwrite=overwrite),
    )
    try:
        report = run_workflow(config)
        typer.echo(f"已输出：{report.output_paths[0]}（{report.rows} 行）")
    except SheetFlowError as exc:
        _fail(exc)


@app.command()
def gui() -> None:
    """启动桌面界面。"""
    try:
        from sheetflow.gui import main

        main()
    except ImportError:
        _fail(RuntimeError("GUI 组件未安装，请安装 sheetflow-tool[gui]"))
