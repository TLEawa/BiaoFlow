import pandas as pd
import pytest

from sheetflow.exceptions import OperationError
from sheetflow.operations import apply_operation


def frame() -> pd.DataFrame:
    return pd.DataFrame(
        {"订单号": [1, 1, 2], "地区": [" 华东 ", " 华东 ", "华南"], "金额": [10, 10, 20]}
    )


def test_trim_and_deduplicate() -> None:
    result = apply_operation(frame(), "trim_text", {})
    result = apply_operation(result, "drop_duplicates", {"columns": ["订单号"]})
    assert result["地区"].tolist() == ["华东", "华南"]


def test_filter_and_sort() -> None:
    result = apply_operation(frame(), "filter", {"column": "金额", "operator": "ge", "value": 10})
    result = apply_operation(result, "sort", {"columns": ["金额"], "ascending": False})
    assert result.iloc[0]["金额"] == 20


def test_group_summary() -> None:
    result = apply_operation(
        frame(), "group_summary", {"group_by": ["地区"], "aggregations": {"金额": "sum"}}
    )
    assert result["金额"].sum() == 40


def test_missing_column() -> None:
    with pytest.raises(OperationError):
        apply_operation(frame(), "drop_columns", {"columns": ["不存在"]})


def test_column_operations_and_fill() -> None:
    source = frame()
    source.loc[0, "地区"] = None
    result = apply_operation(source, "fill_null", {"columns": ["地区"], "value": "未知"})
    result = apply_operation(result, "rename_columns", {"mapping": {"金额": "销售额"}})
    result = apply_operation(result, "reorder_columns", {"columns": ["销售额"]})
    result = apply_operation(result, "drop_columns", {"columns": ["订单号"]})
    assert list(result.columns) == ["销售额", "地区"]
    assert result.loc[0, "地区"] == "未知"


@pytest.mark.parametrize(
    ("operator", "value", "expected"),
    [
        ("eq", 20, 1),
        ("ne", 20, 2),
        ("gt", 10, 1),
        ("le", 10, 2),
        ("in", [10], 2),
    ],
)
def test_filter_operators(operator: str, value: object, expected: int) -> None:
    result = apply_operation(
        frame(), "filter", {"column": "金额", "operator": operator, "value": value}
    )
    assert len(result) == expected


def test_null_filters_and_contains() -> None:
    source = frame()
    source.loc[0, "地区"] = None
    assert len(apply_operation(source, "filter", {"column": "地区", "operator": "isnull"})) == 1
    assert len(apply_operation(source, "filter", {"column": "地区", "operator": "notnull"})) == 2
    assert (
        len(
            apply_operation(
                source,
                "filter",
                {"column": "地区", "operator": "contains", "value": "华南"},
            )
        )
        == 1
    )


def test_type_conversion() -> None:
    source = pd.DataFrame({"数字": ["1", "坏"], "日期": ["2026-01-01", "坏"]})
    number = apply_operation(
        source, "convert_type", {"column": "数字", "target": "integer", "errors": "empty"}
    )
    date = apply_operation(
        source, "convert_type", {"column": "日期", "target": "date", "errors": "keep"}
    )
    assert number.loc[0, "数字"] == 1
    assert pd.isna(number.loc[1, "数字"])
    assert date.loc[1, "日期"] == "坏"


def test_unknown_operations_and_arguments() -> None:
    with pytest.raises(OperationError):
        apply_operation(frame(), "unknown", {})
    with pytest.raises(OperationError):
        apply_operation(frame(), "filter", {"column": "金额", "operator": "bad"})
    with pytest.raises(OperationError):
        apply_operation(frame(), "convert_type", {"column": "金额", "target": "bad"})
    with pytest.raises(OperationError):
        apply_operation(frame(), "group_summary", {"group_by": [], "aggregations": {}})
