from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal, cast

import pandas as pd

from sheetflow.exceptions import OperationError


def _columns(frame: pd.DataFrame, params: dict[str, Any]) -> list[str]:
    values = params.get("columns")
    if values is None:
        return [str(c) for c in frame.columns]
    missing = [c for c in values if c not in frame.columns]
    if missing:
        raise OperationError(f"缺少列：{', '.join(missing)}")
    return list(values)


def apply_operation(
    frame: pd.DataFrame, operation_type: str, params: dict[str, Any]
) -> pd.DataFrame:
    handlers: dict[str, Callable[[pd.DataFrame, dict[str, Any]], pd.DataFrame]] = {
        "drop_empty": _drop_empty,
        "trim_text": _trim_text,
        "rename_columns": _rename_columns,
        "drop_columns": _drop_columns,
        "reorder_columns": _reorder_columns,
        "drop_duplicates": _drop_duplicates,
        "filter": _filter,
        "sort": _sort,
        "convert_type": _convert_type,
        "group_summary": _group_summary,
        "fill_null": _fill_null,
    }
    if operation_type in {"merge", "split_by"}:
        return frame
    handler = handlers.get(operation_type)
    if handler is None:
        raise OperationError(f"未知操作：{operation_type}")
    try:
        return handler(frame.copy(), params)
    except OperationError:
        raise
    except Exception as exc:
        raise OperationError(f"操作 {operation_type} 失败：{exc}") from exc


def _drop_empty(frame: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
    axis = params.get("axis", "both")
    if axis in {"rows", "both"}:
        frame = frame.dropna(axis=0, how="all")
    if axis in {"columns", "both"}:
        frame = frame.dropna(axis=1, how="all")
    return frame.reset_index(drop=True)


def _trim_text(frame: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
    for column in _columns(frame, params):
        frame[column] = frame[column].map(lambda v: v.strip() if isinstance(v, str) else v)
    return frame


def _rename_columns(frame: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
    mapping = params.get("mapping", {})
    missing = [c for c in mapping if c not in frame.columns]
    if missing:
        raise OperationError(f"缺少待重命名列：{', '.join(missing)}")
    return frame.rename(columns=mapping)


def _drop_columns(frame: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
    return frame.drop(columns=_columns(frame, params))


def _reorder_columns(frame: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
    first = _columns(frame, params)
    rest = [c for c in frame.columns if c not in first]
    return frame[first + rest]


def _drop_duplicates(frame: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
    subset = params.get("columns")
    if subset:
        _columns(frame, params)
    return frame.drop_duplicates(subset=subset, keep=params.get("keep", "first")).reset_index(
        drop=True
    )


def _filter(frame: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
    column = params.get("column")
    if column not in frame.columns:
        raise OperationError(f"缺少筛选列：{column}")
    operator = params.get("operator", "eq")
    value = params.get("value")
    series = frame[column]
    comparisons = {
        "eq": lambda: series == value,
        "ne": lambda: series != value,
        "gt": lambda: series > value,
        "ge": lambda: series >= value,
        "lt": lambda: series < value,
        "le": lambda: series <= value,
        "contains": lambda: series.astype(str).str.contains(str(value), regex=False, na=False),
        "in": lambda: series.isin(value if isinstance(value, list) else [value]),
        "isnull": series.isna,
        "notnull": series.notna,
    }
    if operator not in comparisons:
        raise OperationError(f"未知筛选运算符：{operator}")
    return frame[comparisons[operator]()].reset_index(drop=True)


def _sort(frame: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
    columns = _columns(frame, params)
    ascending = params.get("ascending", True)
    return frame.sort_values(columns, ascending=ascending, na_position="last").reset_index(
        drop=True
    )


def _convert_type(frame: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
    column = params.get("column")
    if column not in frame.columns:
        raise OperationError(f"缺少转换列：{column}")
    target = params.get("target", "text")
    errors = params.get("errors", "raise")
    pandas_errors = cast(
        Literal["raise", "coerce"],
        "coerce" if errors in {"empty", "keep"} else "raise",
    )
    original = frame[column].copy()
    converted: pd.Series[Any]
    if target == "text":
        converted = frame[column].astype("string")
    elif target in {"integer", "number"}:
        converted = pd.to_numeric(frame[column], errors=pandas_errors)
        if target == "integer":
            converted = converted.astype("Int64")
    elif target == "date":
        converted = pd.to_datetime(frame[column], errors=pandas_errors)
    else:
        raise OperationError(f"未知目标类型：{target}")
    if errors == "keep":
        converted = converted.where(converted.notna(), original)
    frame[column] = converted
    return frame


def _group_summary(frame: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
    group_by = params.get("group_by", [])
    aggregations = params.get("aggregations", {})
    missing = [c for c in [*group_by, *aggregations] if c not in frame.columns]
    if missing:
        raise OperationError(f"汇总缺少列：{', '.join(missing)}")
    if not group_by or not aggregations:
        raise OperationError("分组汇总需要 group_by 和 aggregations")
    return frame.groupby(group_by, dropna=False).agg(aggregations).reset_index()


def _fill_null(frame: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
    for column in _columns(frame, params):
        frame[column] = frame[column].fillna(params.get("value"))
    return frame
