from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd

from sheetflow.config import OutputConfig, WorkflowConfig
from sheetflow.exceptions import OperationError
from sheetflow.exporters import export_table
from sheetflow.readers import read_table
from sheetflow.service import TaskReport, resolve_inputs

STANDARD_FIELDS = ["order_id", "shop_name", "product_name", "sku", "quantity", "price", "amount", "status", "buyer", "province", "city", "created_at"]
ALIASES = {
    "order_id": ["订单号", "订单编号", "交易编号", "Order ID", "order_id", "订单ID"],
    "shop_name": ["店铺", "店铺名称", "店名", "shop", "shop_name"],
    "product_name": ["商品", "商品名称", "产品名称", "product_name"],
    "sku": ["SKU", "商品编码", "货号", "sku"],
    "quantity": ["数量", "商品数量", "件数", "quantity"],
    "price": ["单价", "价格", "price"],
    "amount": ["金额", "销售额", "实付金额", "amount", "订单金额"],
    "status": ["状态", "订单状态", "status"],
    "buyer": ["买家", "客户", "buyer"],
    "province": ["省份", "省", "province"],
    "city": ["城市", "市", "city"],
    "created_at": ["下单时间", "创建时间", "created_at"],
}

def infer_mapping(columns: list[str]) -> dict[str, str]:
    normalized = {re.sub(r"\s+", "", str(c)).lower(): str(c) for c in columns}
    result: dict[str, str] = {}
    for field, aliases in ALIASES.items():
        for alias in aliases:
            key = re.sub(r"\s+", "", alias).lower()
            if key in normalized:
                result[field] = normalized[key]
                break
    return result

def normalize_frame(frame: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    missing = [name for name in ("order_id", "shop_name", "quantity", "amount") if name not in mapping]
    if missing:
        labels = {"order_id": "订单号", "shop_name": "店铺", "quantity": "数量", "amount": "金额"}
        raise OperationError("找不到关键字段：" + "、".join(labels[x] for x in missing) + "。请在字段映射中选择对应列。")
    rename = {source: target for target, source in mapping.items() if source in frame.columns}
    return frame.rename(columns=rename)

def run_ecommerce(config: WorkflowConfig, mapping: dict[str, str] | None = None) -> TaskReport:
    paths = resolve_inputs(config.input.paths)
    if not paths:
        raise OperationError("没有找到可处理的订单文件")
    mapping = mapping or config.mapping
    frames = []
    report = TaskReport(input_count=len(paths))
    for path in paths:
        frame = normalize_frame(read_table(path, sheet=config.input.sheet, header=config.input.header, encoding=config.input.encoding, delimiter=config.input.delimiter), mapping or {})
        frame["来源文件"] = path.name
        frames.append(frame)
        report.success_count += 1
    raw = pd.concat(frames, ignore_index=True, sort=False)
    before = len(raw)
    raw = raw.dropna(how="all").copy()
    raw = raw[raw["order_id"].notna() & raw["order_id"].astype(str).str.strip().ne("")]
    raw = raw.drop_duplicates(subset=["order_id"], keep="first")
    if "status" in raw.columns:
        invalid = {"已取消", "取消", "退款", "已退款", "作废"}
        raw = raw[~raw["status"].astype(str).str.strip().isin(invalid)]
    raw["quantity"] = pd.to_numeric(raw["quantity"], errors="coerce").fillna(0)
    raw["amount"] = pd.to_numeric(raw["amount"], errors="coerce").fillna(0)
    summary = raw.groupby("shop_name", dropna=False).agg(订单数=("order_id", "nunique"), 商品数量=("quantity", "sum"), 销售额=("amount", "sum")).reset_index()
    output = Path(config.output.path)
    output.parent.mkdir(parents=True, exist_ok=True)
    report.output_paths.append(export_table(raw, config.output, output))
    summary_cfg = OutputConfig(path=str(output.with_name("订单汇总.xlsx")), format="xlsx", overwrite=True)
    report.output_paths.append(export_table(summary, summary_cfg))
    split_dir = output.parent / "按店铺拆分"
    split_dir.mkdir(parents=True, exist_ok=True)
    for value, part in raw.groupby("shop_name", dropna=False):
        safe = re.sub(r'[<>:"/\\|?*]+', "_", str(value))[:60] or "空值"
        report.output_paths.append(export_table(part.reset_index(drop=True), OutputConfig(path=str(split_dir / f"{safe}.xlsx"), format="xlsx", overwrite=True)))
    report.rows = len(raw)
    report.before_rows = before
    report.removed_rows = before - len(raw)
    report.summary = {"sales_amount": float(raw["amount"].sum()), "summary_rows": len(summary)}
    return report
