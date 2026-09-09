from sheetflow.assistant import suggest_operations, template_operations


def test_chinese_instruction_generates_reviewable_workflow() -> None:
    suggestion = suggest_operations(
        "合并文件并保留来源，按手机号去重，再按城市拆分",
        ["手机号", "城市", "姓名"],
    )
    assert suggestion.warnings == []
    assert [operation.type for operation in suggestion.operations] == [
        "merge",
        "drop_duplicates",
        "split_by",
    ]
    assert suggestion.operations[0].params()["add_source_column"] is True
    assert suggestion.operations[1].params()["columns"] == ["手机号"]
    assert suggestion.operations[2].params()["column"] == "城市"


def test_group_summary_understands_group_and_value_columns() -> None:
    suggestion = suggest_operations("按地区汇总销售额", ["地区", "销售额"])
    operation = suggestion.operations[0]
    assert operation.type == "group_summary"
    assert operation.params()["group_by"] == ["地区"]
    assert operation.params()["aggregations"] == {"销售额": "sum"}


def test_unknown_column_is_not_guessed() -> None:
    suggestion = suggest_operations("按城市拆分", ["地区", "金额"])
    assert suggestion.operations == []
    assert any("无法确定" in warning for warning in suggestion.warnings)


def test_ecommerce_template_uses_existing_order_column() -> None:
    suggestion = template_operations("电商订单整理", ["订单号", "金额"])
    deduplicate = suggestion.operations[-1]
    assert deduplicate.params()["columns"] == ["订单号"]


def test_other_templates_are_available_without_column_guessing() -> None:
    generic = template_operations("通用表格清洗")
    customers = template_operations("客户名单去重", ["手机号", "姓名"])
    attendance = template_operations("考勤表合并")
    missing = template_operations("不存在的模板")
    assert [operation.type for operation in generic.operations] == [
        "merge",
        "drop_empty",
        "trim_text",
        "drop_duplicates",
    ]
    assert customers.operations[-1].params()["columns"] == ["手机号"]
    assert attendance.operations[0].type == "merge"
    assert missing.operations == []
    assert missing.warnings


def test_common_editing_phrases() -> None:
    columns = ["姓名", "城市", "金额", "备注"]
    suggestion = suggest_operations(
        "清理姓名空格，按金额降序排序，删除备注列，把城市改成地区",
        columns,
    )
    assert [operation.type for operation in suggestion.operations] == [
        "trim_text",
        "sort",
        "drop_columns",
        "rename_columns",
    ]
    assert suggestion.operations[1].params()["ascending"] is False
    assert suggestion.operations[3].params()["mapping"] == {"城市": "地区"}


def test_empty_instruction_returns_clear_warning() -> None:
    suggestion = suggest_operations("   ")
    assert suggestion.operations == []
    assert suggestion.warnings == ["请先输入处理需求"]
