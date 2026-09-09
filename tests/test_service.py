from pathlib import Path

import pandas as pd
import pytest

from sheetflow.config import InputConfig, OperationConfig, OutputConfig, WorkflowConfig
from sheetflow.exceptions import TaskCancelled
from sheetflow.service import run_workflow


def config(inputs: list[Path], output: Path, on_error: str = "stop") -> WorkflowConfig:
    return WorkflowConfig(
        version=1,
        input=InputConfig(paths=[str(path) for path in inputs], on_error=on_error),
        operations=[
            OperationConfig(type="merge", add_source_column=True),
            OperationConfig(type="drop_duplicates", columns=["编号"]),
        ],
        output=OutputConfig(path=str(output)),
    )


def test_full_workflow_with_partial_failure(tmp_path: Path) -> None:
    good = tmp_path / "数据.csv"
    bad = tmp_path / "坏.xlsx"
    good.write_text("编号,值\n1,A\n1,A\n2,B\n", encoding="utf-8")
    bad.write_bytes(b"not an excel file")
    output = tmp_path / "结果.xlsx"
    report = run_workflow(config([good, bad], output, "continue"))
    assert report.success_count == 1
    assert report.skipped_count == 1
    assert len(pd.read_excel(output)) == 2


def test_cancel_before_read(tmp_path: Path) -> None:
    source = tmp_path / "a.csv"
    source.write_text("编号\n1\n", encoding="utf-8")
    with pytest.raises(TaskCancelled):
        run_workflow(config([source], tmp_path / "out.csv"), cancelled=lambda: True)


def test_split(tmp_path: Path) -> None:
    source = tmp_path / "a.csv"
    source.write_text("地区,值\n华东,1\n华南,2\n", encoding="utf-8")
    workflow = WorkflowConfig(
        version=1,
        input=InputConfig(paths=[str(source)]),
        operations=[OperationConfig(type="split_by", column="地区")],
        output=OutputConfig(path=str(tmp_path / "订单.xlsx")),
    )
    report = run_workflow(workflow)
    assert {path.name for path in report.output_paths} == {"订单_华东.xlsx", "订单_华南.xlsx"}
