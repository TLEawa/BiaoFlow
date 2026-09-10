from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from sheetflow.config import OperationConfig


@dataclass
class WorkflowSuggestion:
    operations: list[OperationConfig] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class WorkflowTemplate:
    name: str
    description: str


TEMPLATES: dict[str, WorkflowTemplate] = {
    "电商订单整理": WorkflowTemplate(
        name="电商订单整理",
        description="合并订单、保留来源、清理空白并按订单号去重，再按省份拆分发货表。",
    ),
    "通用表格清洗": WorkflowTemplate(
        name="通用表格清洗",
        description="合并文件、删除空行空列、清理文本空格并去重。",
    ),
    "客户名单去重": WorkflowTemplate(
        name="客户名单去重",
        description="清理客户信息中的空格，优先按手机号或电话去重。",
    ),
    "考勤表合并": WorkflowTemplate(
        name="考勤表合并",
        description="合并多份考勤表、保留来源并清理空行和文本空格。",
    ),
}


def template_operations(name: str, columns: list[str] | None = None) -> WorkflowSuggestion:
    known = columns or []
    if name not in TEMPLATES:
        return WorkflowSuggestion(warnings=[f"未知模板：{name}"])

    if name == "通用表格清洗":
        raw = [
            {"type": "merge", "add_source_column": True},
            {"type": "drop_empty", "axis": "both"},
            {"type": "trim_text"},
            {"type": "drop_duplicates"},
        ]
    elif name == "电商订单整理":
        order_column = _first_matching_column(known, ["订单号", "订单编号", "order_id", "id"])
        deduplicate: dict[str, Any] = {"type": "drop_duplicates"}
        if order_column:
            deduplicate["columns"] = [order_column]
        raw = [
            {"type": "merge", "add_source_column": True},
            {"type": "drop_empty", "axis": "both"},
            {"type": "trim_text"},
            deduplicate,
        ]
    elif name == "客户名单去重":
        contact_column = _first_matching_column(
            known, ["手机号", "手机", "电话", "联系电话", "phone", "mobile"]
        )
        deduplicate = {"type": "drop_duplicates"}
        if contact_column:
            deduplicate["columns"] = [contact_column]
        raw = [{"type": "trim_text"}, deduplicate]
    else:
        raw = [
            {"type": "merge", "add_source_column": True},
            {"type": "drop_empty", "axis": "rows"},
            {"type": "trim_text"},
        ]
    return WorkflowSuggestion(operations=[OperationConfig.model_validate(item) for item in raw])


def suggest_operations(instruction: str, columns: list[str] | None = None) -> WorkflowSuggestion:
    """把常见中文表格需求转换为可复核的本地工作流。

    该功能是确定性规则解析器，不会上传用户数据，也不会声称已理解
    未能明确识别的要求。
    """
    result = WorkflowSuggestion()
    known = [str(column) for column in (columns or [])]
    text = instruction.strip()
    if not text:
        result.warnings.append("请先输入处理需求")
        return result

    clauses = [
        value.strip()
        for value in re.split(r"(?:然后|接着|之后|再|，|,|；|;|\n)+", text)
        if value.strip()
    ]
    for clause in clauses:
        operation = _parse_clause(clause, known, result.warnings)
        if operation is not None:
            result.operations.append(OperationConfig.model_validate(operation))

    if not result.operations:
        result.warnings.append("暂时没有识别出可执行步骤，请换用更具体的表述")
    return result


def _parse_clause(
    clause: str, columns: list[str], warnings: list[str]
) -> dict[str, Any] | None:
    if "合并" in clause:
        return {
            "type": "merge",
            "add_source_column": any(word in clause for word in ("来源", "文件名")),
        }
    if "空行" in clause or "空列" in clause:
        if "空行" in clause and "空列" in clause:
            axis = "both"
        elif "空列" in clause:
            axis = "columns"
        else:
            axis = "rows"
        return {"type": "drop_empty", "axis": axis}
    if any(word in clause for word in ("空格", "首尾空白", "文本清理")):
        matched = _columns_mentioned(clause, columns)
        operation: dict[str, Any] = {"type": "trim_text"}
        if matched:
            operation["columns"] = matched
        return operation
    if "去重" in clause or "重复行" in clause:
        matched = _columns_mentioned(clause, columns)
        operation = {"type": "drop_duplicates"}
        if matched:
            operation["columns"] = matched
        return operation
    if "拆分" in clause or "分成多个文件" in clause:
        column = _single_required_column(clause, columns, "拆分", warnings)
        return {"type": "split_by", "column": column} if column else None
    if "排序" in clause or "升序" in clause or "降序" in clause:
        column = _single_required_column(clause, columns, "排序", warnings)
        if not column:
            return None
        return {"type": "sort", "columns": [column], "ascending": "降序" not in clause}
    if "删除列" in clause or ("删除" in clause and "列" in clause):
        matched = _columns_mentioned(clause, columns)
        if not matched:
            warnings.append(f"无法确定要删除的列：{clause}")
            return None
        return {"type": "drop_columns", "columns": matched}
    rename = re.search(r"(?:把|将)?(.+?)(?:列)?(?:改成|改为|重命名为)(.+?)(?:列)?$", clause)
    if rename:
        source = _best_column(rename.group(1), columns)
        target = rename.group(2).strip().strip("“”\"'")
        if source and target:
            return {"type": "rename_columns", "mapping": {source: target}}
        warnings.append(f"无法确定重命名的列：{clause}")
        return None
    if "汇总" in clause or "分组统计" in clause:
        matched = _columns_mentioned(clause, columns)
        if len(matched) < 2:
            warnings.append(f"汇总需要同时说明分组列和数值列：{clause}")
            return None
        group_text = clause.split("汇总", 1)[0].split("分组统计", 1)[0]
        group_column = _best_column(group_text, columns) or matched[0]
        value_column = next(column for column in matched if column != group_column)
        aggregation = "mean" if any(word in clause for word in ("平均", "均值")) else "sum"
        return {
            "type": "group_summary",
            "group_by": [group_column],
            "aggregations": {value_column: aggregation},
        }
    return None


def _columns_mentioned(text: str, columns: list[str]) -> list[str]:
    return [column for column in sorted(columns, key=len, reverse=True) if column in text]


def _best_column(text: str, columns: list[str]) -> str | None:
    matched = _columns_mentioned(text, columns)
    return matched[0] if matched else None


def _single_required_column(
    clause: str, columns: list[str], action: str, warnings: list[str]
) -> str | None:
    matched = _columns_mentioned(clause, columns)
    if matched:
        return matched[0]
    warnings.append(f"无法确定{action}使用的列：{clause}")
    return None


def _first_matching_column(columns: list[str], candidates: list[str]) -> str | None:
    lowered = {column.casefold(): column for column in columns}
    for candidate in candidates:
        if candidate.casefold() in lowered:
            return lowered[candidate.casefold()]
    return None
