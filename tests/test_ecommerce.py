from pathlib import Path

import pandas as pd
import pytest

from sheetflow.config import InputConfig, OperationConfig, OutputConfig, WorkflowConfig
from sheetflow.ecommerce import infer_mapping, normalize_frame, run_ecommerce
from sheetflow.exceptions import OperationError


def test_infer_mapping_and_missing_key():
    mapping = infer_mapping(["订单编号", "店铺名称", "数量", "销售额"])
    assert mapping["order_id"] == "订单编号"
    assert normalize_frame(pd.DataFrame({"订单编号": ["A"]}), mapping).columns[0] == "order_id"
    with pytest.raises(OperationError):
        normalize_frame(pd.DataFrame({"订单编号": ["A"]}), {"order_id": "订单编号"})


def test_ecommerce_outputs(tmp_path: Path):
    source = tmp_path / "订单.csv"
    pd.DataFrame(
        {
            "订单号": ["A", "A", "B"],
            "店铺": ["甲", "甲", "乙"],
            "数量": [1, 1, 2],
            "金额": [10, 10, 20],
            "状态": ["已付款", "已付款", "已取消"],
        }
    ).to_csv(source, index=False, encoding="utf-8-sig")
    cfg = WorkflowConfig(
        version=1,
        input=InputConfig(paths=[str(source)]),
        operations=[OperationConfig(type="ecommerce_workflow")],
        output=OutputConfig(path=str(tmp_path / "全部订单.xlsx"), overwrite=True),
        mapping=infer_mapping(["订单号", "店铺", "数量", "金额", "状态"]),
    )
    report = run_ecommerce(cfg)
    assert report.rows == 1
    assert (tmp_path / "订单汇总.xlsx").exists()
    assert (tmp_path / "按店铺拆分" / "甲.xlsx").exists()


def test_mixed_files_use_individual_field_mapping(tmp_path: Path):
    csv_path = tmp_path / "中文订单.csv"
    xlsx_path = tmp_path / "另一平台.xlsx"
    pd.DataFrame(
        {"订单号": ["A1"], "店铺": ["甲"], "数量": [1], "金额": [10], "省份": ["广东"]}
    ).to_csv(csv_path, index=False, encoding="utf-8-sig")
    pd.DataFrame(
        {
            "交易编号": ["B1"],
            "店铺名称": ["乙"],
            "商品数量": [2],
            "销售额": [30],
            "省": ["浙江"],
        }
    ).to_excel(xlsx_path, index=False)
    cfg = WorkflowConfig(
        version=1,
        input=InputConfig(paths=[str(csv_path), str(xlsx_path)]),
        operations=[OperationConfig(type="ecommerce_workflow")],
        output=OutputConfig(path=str(tmp_path / "全部订单.xlsx"), overwrite=True),
    )
    report = run_ecommerce(cfg)
    assert report.rows == 2
    assert (tmp_path / "按地区拆分" / "广东.xlsx").exists()
    assert (tmp_path / "按地区拆分" / "浙江.xlsx").exists()
