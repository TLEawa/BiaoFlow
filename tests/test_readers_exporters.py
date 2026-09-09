from pathlib import Path

import pandas as pd
import pytest

from sheetflow.config import OutputConfig
from sheetflow.exceptions import ExportError
from sheetflow.exporters import export_table
from sheetflow.readers import inspect_table, read_table


def test_read_gbk_csv(tmp_path: Path) -> None:
    path = tmp_path / "中文 文件.csv"
    path.write_text("名称;数量\n苹果;2\n", encoding="gbk")
    result = read_table(path)
    assert result.loc[0, "名称"] == "苹果"


@pytest.mark.parametrize("suffix", [".csv", ".xlsx"])
def test_export_roundtrip_and_overwrite_guard(tmp_path: Path, suffix: str) -> None:
    target = tmp_path / f"结果{suffix}"
    config = OutputConfig(path=str(target))
    export_table(pd.DataFrame({"列": [1, 2]}), config)
    assert read_table(target)["列"].tolist() == [1, 2]
    with pytest.raises(ExportError):
        export_table(pd.DataFrame({"列": [3]}), config)


def test_inspect(tmp_path: Path) -> None:
    path = tmp_path / "a.csv"
    path.write_text("a,b\n1,2\n", encoding="utf-8")
    assert inspect_table(path)["rows"] == 1
