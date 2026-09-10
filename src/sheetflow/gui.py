from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QDragEnterEvent, QDropEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from sheetflow.assistant import (
    TEMPLATES,
    WorkflowSuggestion,
    suggest_operations,
    template_operations,
)
from sheetflow.config import (
    InputConfig,
    OperationConfig,
    OutputConfig,
    WorkflowConfig,
    load_workflow,
    save_workflow,
)
from sheetflow.ecommerce import run_ecommerce
from sheetflow.exceptions import SheetFlowError
from sheetflow.readers import read_table
from sheetflow.service import TaskReport, preview_workflow, run_workflow

PRESETS: dict[str, dict[str, object]] = {
    "合并文件": {"type": "merge", "add_source_column": True},
    "删除空行和空列": {"type": "drop_empty", "axis": "both"},
    "清理文本空格": {"type": "trim_text"},
    "删除重复行": {"type": "drop_duplicates"},
    "重命名列": {"type": "rename_columns", "mapping": {"旧列名": "新列名"}},
    "删除列": {"type": "drop_columns", "columns": ["列名"]},
    "调整列顺序": {"type": "reorder_columns", "columns": ["列名"]},
    "筛选行": {"type": "filter", "column": "列名", "operator": "eq", "value": "值"},
    "排序": {"type": "sort", "columns": ["列名"], "ascending": True},
    "类型转换": {"type": "convert_type", "column": "列名", "target": "number"},
    "填充空值": {"type": "fill_null", "columns": ["列名"], "value": ""},
    "分组汇总": {
        "type": "group_summary",
        "group_by": ["分组列"],
        "aggregations": {"数值列": "sum"},
    },
    "按列拆分文件": {"type": "split_by", "column": "列名"},
}


class ThemedComboBox(QComboBox):
    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#45658c"), 1.5))
        x, y = self.width() - 17, self.height() // 2
        painter.drawLine(x - 4, y - 2, x, y + 2)
        painter.drawLine(x, y + 2, x + 4, y - 2)
        painter.end()


class FileListWidget(QListWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.is_dir() or path.suffix.lower() in {".csv", ".xlsx"}:
                self.addItem(str(path))
        event.acceptProposedAction()


class Worker(QThread):
    progress = Signal(int, str)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, config: WorkflowConfig) -> None:
        super().__init__()
        self.config = config
        self.cancel_requested = False

    def run(self) -> None:
        try:
            if self.config.operations and self.config.operations[0].type == "ecommerce_workflow":
                report = run_ecommerce(self.config)
            else:
                report = run_workflow(
                    self.config,
                    progress=lambda value, text: self.progress.emit(value, text),
                    cancelled=lambda: self.cancel_requested,
                )
            self.completed.emit(report)
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("表流 BiaoFlow 0.3.0 · 电商订单批处理")
        self.resize(1280, 860)
        self.setMinimumSize(980, 680)
        self.worker: Worker | None = None
        self.files = FileListWidget()
        self.operations = QListWidget()
        self.operation_editor = QPlainTextEdit()
        self.operation_editor.setPlaceholderText(
            '选中操作后可编辑 JSON 参数，例如 {"type":"trim_text"}'
        )
        self.operation_editor.setMaximumHeight(90)
        self.preview = QTableWidget()
        self.output_label = QLabel("尚未选择输出文件")
        self.output_path: str | None = None
        self.ecommerce_mode = False
        self.progress_bar = QProgressBar()
        self.status = QLabel("就绪")
        self.instruction = QPlainTextEdit()
        self.instruction.setPlaceholderText(
            "例如：合并文件并保留来源，删除空行空列，按手机号去重，再按城市拆分"
        )
        self.instruction.setMaximumHeight(64)
        self.template_combo = ThemedComboBox()
        self.template_combo.addItems(list(TEMPLATES))
        self._build_ui()
        self.setStyleSheet("""
            QMainWindow { background: #f3f6fb; }
            QMessageBox { background: #f3f6fb; }
            QMessageBox QLabel { color: #24334b; background: transparent;
                font-size: 14px; min-height: 28px; }
            QMessageBox QPushButton { background: white; color: #24334b;
                border: 1px solid #cbd8eb; min-width: 76px; padding: 8px 16px; }
            QMessageBox QPushButton:default { background: #2563eb; color: white;
                border: 1px solid #2563eb; }
            QMessageBox QPushButton:hover { background: #dbeafe; color: #19365e; }
            QMessageBox QPushButton:focus { border: 2px solid #7299ce; }
            QWidget#settingsPanel { background: #f3f6fb; }
            QWidget { font-family: 'Microsoft YaHei UI'; font-size: 13px; color: #24334b; }
            QGroupBox { background: white; border: 1px solid #dce4ef;
                border-radius: 10px; margin-top: 16px; padding: 16px 12px 12px; }
            QGroupBox::title { subcontrol-origin: margin; left: 14px; font-weight: 600; }
            QPushButton { background: white; border: 1px solid #d2dcea;
                border-radius: 6px; padding: 8px 12px; }
            QPushButton:hover { background: #eef4ff; border-color: #91b5f4; }
            QPushButton:disabled { color: #96a2b5; background: #edf1f6; }
            QPushButton#primary { background: #2563eb; color: white; border: 0;
                font-weight: 600; padding: 11px 24px; }
            QPushButton#primary:hover { background: #1d4ed8; }
            QPushButton#primary:disabled { background: #a9bce2; }
            QListWidget, QPlainTextEdit, QTableWidget, QComboBox {
                background: white; border: 1px solid #dce4ef; border-radius: 6px;
                selection-background-color: #dbeafe; selection-color: #19365e; }
            QListWidget::item { padding: 8px; }
            QComboBox { padding: 7px 32px 7px 10px; }
            QComboBox:hover, QComboBox:focus { border-color: #91b5f4;
                background: #eef4ff; }
            QComboBox::drop-down { subcontrol-origin: padding;
                subcontrol-position: top right; width: 28px; border: 0;
                background: transparent; }
            QComboBox::down-arrow { image: none; width: 0px; height: 0px; border: 0; }
            QComboBox QAbstractItemView { background: white; color: #24334b;
                border: 1px solid #d2dcea; padding: 4px;
                selection-background-color: #dbeafe; selection-color: #19365e;
                outline: 0; }
            QComboBox QAbstractItemView::item { min-height: 30px; padding: 4px 8px; }
            QComboBox QAbstractItemView::item:selected { background: #dbeafe;
                color: #19365e; border-radius: 4px; }
            QHeaderView::section { background: #edf2fa; border: 0;
                border-bottom: 1px solid #dce4ef; padding: 8px; font-weight: 600; }
            QTableWidget { alternate-background-color: #f7f9fd; gridline-color: #edf1f6; }
            QProgressBar { border: 0; border-radius: 3px; background: #e1e8f2;
                max-height: 6px; min-height: 6px; }
            QProgressBar::chunk { background: #2563eb; border-radius: 3px; }
            QSplitter::handle { background: #f3f6fb; width: 12px; }
            QScrollArea { border: 0; background: transparent; }
            QScrollBar:vertical { background: #edf2fa; width: 12px;
                margin: 3px 2px; border-radius: 4px; }
            QScrollBar::handle:vertical { background: #a9bfdf;
                min-height: 28px; border-radius: 4px; }
            QScrollBar::handle:vertical:hover { background: #7299ce; }
            QScrollBar::handle:vertical:pressed { background: #2563eb; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent; }
        """)

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(14)
        title = QLabel("表流 BiaoFlow  ·  电商订单批处理")
        title.setStyleSheet("font-size: 25px; font-weight: 700; color: #152945;")
        layout.addWidget(title)
        subtitle = QLabel("订单文件 → 自动整理 → 预览发货表 → 导出    ·    本地处理，数据不上传")
        subtitle.setStyleSheet("color: #64748b;")
        layout.addWidget(subtitle)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter, 1)
        settings = QWidget()
        settings.setObjectName("settingsPanel")
        settings_layout = QVBoxLayout(settings)
        settings_layout.setContentsMargins(0, 0, 8, 0)
        settings_layout.setSpacing(14)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(settings)
        splitter.addWidget(scroll)
        input_group = QGroupBox("01  导入文件")
        input_layout = QVBoxLayout(input_group)
        file_buttons = QHBoxLayout()
        add_file = QPushButton("添加文件")
        add_dir = QPushButton("添加目录")
        clear = QPushButton("清空")
        add_file.clicked.connect(self.add_files)
        add_dir.clicked.connect(self.add_directory)
        clear.clicked.connect(self.files.clear)
        for button in (add_file, add_dir, clear):
            file_buttons.addWidget(button)
        input_layout.addLayout(file_buttons)
        input_layout.addWidget(QLabel("支持 CSV / XLSX，可拖入文件或整个文件夹"))
        self.files.setMinimumHeight(90)
        self.files.setMaximumHeight(140)
        self.files.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        input_layout.addWidget(self.files)
        settings_layout.addWidget(input_group)

        assistant_row = QHBoxLayout()
        generate = QPushButton("从描述生成步骤")
        apply_template = QPushButton("应用模板")
        generate.clicked.connect(self.generate_operations)
        apply_template.clicked.connect(self.apply_template)
        assistant_row.addWidget(self.template_combo)
        assistant_row.addWidget(apply_template)
        assistant_row.addWidget(generate)
        assistant_group = QGroupBox("02  用一句话创建流程")
        assistant_layout = QVBoxLayout(assistant_group)
        self.instruction.setMinimumHeight(64)
        assistant_layout.addWidget(self.instruction)
        assistant_layout.addLayout(assistant_row)
        settings_layout.addWidget(assistant_group)

        operation_row = QHBoxLayout()
        preset = ThemedComboBox()
        preset.addItems(list(PRESETS))
        add_operation = QPushButton("添加操作")
        remove_operation = QPushButton("删除操作")
        up = QPushButton("上移")
        down = QPushButton("下移")
        add_operation.clicked.connect(lambda: self.add_operation(preset.currentText()))
        remove_operation.clicked.connect(self.remove_operation)
        up.clicked.connect(lambda: self.move_operation(-1))
        down.clicked.connect(lambda: self.move_operation(1))
        self.operations.currentRowChanged.connect(self.show_operation)
        self.operation_editor.textChanged.connect(self.update_operation)
        for widget in (preset, add_operation):
            operation_row.addWidget(widget)
        operation_group = QGroupBox("03  编辑处理步骤")
        operation_layout = QVBoxLayout(operation_group)
        operation_layout.addLayout(operation_row)
        self.operations.setMinimumHeight(100)
        self.operations.setMaximumHeight(180)
        self.operations.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.operations.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        operation_layout.addWidget(self.operations)
        reorder_row = QHBoxLayout()
        for widget in (remove_operation, up, down):
            reorder_row.addWidget(widget)
        operation_layout.addLayout(reorder_row)
        details = QPushButton("展开高级参数（JSON）")
        details.setCheckable(True)
        self.operation_editor.setVisible(False)
        details.toggled.connect(self.operation_editor.setVisible)
        details.toggled.connect(
            lambda checked: details.setText(
                "收起高级参数（JSON）" if checked else "展开高级参数（JSON）"
            )
        )
        operation_layout.addWidget(details)
        operation_layout.addWidget(self.operation_editor)
        settings_layout.addWidget(operation_group)
        settings_layout.addStretch()

        action_row = QHBoxLayout()
        preview = QPushButton("预览前 100 行")
        choose_output = QPushButton("选择输出文件")
        save = QPushButton("保存工作流")
        load = QPushButton("打开工作流")
        run = QPushButton("开始处理")
        cancel = QPushButton("取消")
        self.run_button = run
        self.cancel_button = cancel
        cancel.setEnabled(False)
        run.setObjectName("primary")
        preview.clicked.connect(self.load_preview)
        choose_output.clicked.connect(self.choose_output)
        save.clicked.connect(self.save_config)
        load.clicked.connect(self.load_config)
        run.clicked.connect(self.start_task)
        cancel.clicked.connect(self.cancel_task)
        preview_group = QGroupBox("04  数据预览")
        preview_layout = QVBoxLayout(preview_group)
        preview_toolbar = QHBoxLayout()
        preview_toolbar.addWidget(QLabel("执行当前步骤后，展示前 100 行结果"))
        preview_toolbar.addStretch()
        preview_toolbar.addWidget(preview)
        preview_layout.addLayout(preview_toolbar)
        self.preview_hint = QLabel("还没有预览数据\n\n添加文件并设置步骤后，点击「预览前 100 行」")
        self.preview_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_hint.setStyleSheet("color: #75869e; font-size: 15px;")
        preview_layout.addWidget(self.preview_hint, 1)
        self.preview.setVisible(False)
        self.preview.setAlternatingRowColors(True)
        self.preview.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.preview.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.preview.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.preview.horizontalHeader().setStretchLastSection(True)
        preview_layout.addWidget(self.preview, 1)
        splitter.addWidget(preview_group)
        splitter.setSizes([460, 760])
        splitter.setChildrenCollapsible(False)
        output_group = QGroupBox("导出设置")
        output_layout = QHBoxLayout(output_group)
        self.output_label.setWordWrap(True)
        output_layout.addWidget(self.output_label, 1)
        output_layout.addWidget(choose_output)
        layout.addWidget(output_group)
        for button in (load, save):
            action_row.addWidget(button)
        action_row.addStretch()
        action_row.addWidget(cancel)
        action_row.addWidget(run)
        layout.addLayout(action_row)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.setCentralWidget(root)

    def add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "选择文件", "", "表格 (*.csv *.xlsx)")
        for path in paths:
            self.files.addItem(path)

    def add_directory(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择目录")
        if path:
            self.files.addItem(path)

    def add_operation(self, label: str) -> None:
        self.append_operation(json.dumps(PRESETS[label], ensure_ascii=False))

    def append_operation(self, raw: str) -> None:
        item = QListWidgetItem()
        self.set_operation_data(item, raw)
        self.operations.addItem(item)

    def set_operation_data(self, item: QListWidgetItem, raw: str) -> None:
        item.setData(Qt.ItemDataRole.UserRole, raw)
        try:
            data = json.loads(raw)
            label = next(
                (name for name, preset in PRESETS.items() if preset["type"] == data["type"]),
                "自定义步骤",
            )
            columns = data.get("columns") or data.get("group_by")
            if columns:
                label += " · " + "、".join(str(value) for value in columns)
            elif data.get("column"):
                label += " · " + str(data["column"])
            item.setText(label)
        except (ValueError, TypeError, KeyError):
            item.setText("参数格式有误 · 请展开高级参数修正")

    def _available_columns(self) -> list[str]:
        if self.files.count() == 0:
            return []
        source = Path(self.files.item(0).text())
        if source.is_dir():
            source = next(
                (p for p in source.iterdir() if p.suffix.lower() in {".csv", ".xlsx"}),
                source,
            )
        if not source.is_file():
            return []
        return [str(column) for column in read_table(source).columns]

    def _set_suggestion(self, suggestion: WorkflowSuggestion) -> None:
        operations = suggestion.operations
        warnings = suggestion.warnings
        if operations:
            self.operations.clear()
            for operation in operations:
                self.append_operation(json.dumps(operation.model_dump(), ensure_ascii=False))
        if warnings:
            self.status.setText("；".join(warnings))
        elif operations:
            self.status.setText(f"已生成 {len(operations)} 个处理步骤，请预览后再执行")

    def generate_operations(self) -> None:
        try:
            suggestion = suggest_operations(
                self.instruction.toPlainText(), self._available_columns()
            )
            self._set_suggestion(suggestion)
        except Exception as exc:
            QMessageBox.warning(self, "生成失败", str(exc))

    def apply_template(self) -> None:
        try:
            suggestion = template_operations(
                self.template_combo.currentText(), self._available_columns()
            )
            self._set_suggestion(suggestion)
            self.instruction.setPlainText(TEMPLATES[self.template_combo.currentText()].description)
            if self.template_combo.currentText() == "电商订单整理":
                self.ecommerce_mode = True
                self.operations.clear()
                self.append_operation(
                    json.dumps({"type": "ecommerce_workflow"}, ensure_ascii=False)
                )
                self.status.setText("已应用电商订单整理：添加文件后即可开始处理")
            else:
                self.ecommerce_mode = False
        except Exception as exc:
            QMessageBox.warning(self, "无法应用模板", str(exc))

    def remove_operation(self) -> None:
        self.operations.takeItem(self.operations.currentRow())

    def move_operation(self, offset: int) -> None:
        row = self.operations.currentRow()
        target = row + offset
        if row >= 0 and 0 <= target < self.operations.count():
            item = self.operations.takeItem(row)
            self.operations.insertItem(target, item)
            self.operations.setCurrentRow(target)

    def show_operation(self, row: int) -> None:
        self.operation_editor.blockSignals(True)
        self.operation_editor.setPlainText(
            self.operations.item(row).data(Qt.ItemDataRole.UserRole) if row >= 0 else ""
        )
        self.operation_editor.blockSignals(False)

    def update_operation(self) -> None:
        row = self.operations.currentRow()
        if row >= 0:
            self.set_operation_data(self.operations.item(row), self.operation_editor.toPlainText())

    def choose_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "输出文件", "result.xlsx", "Excel (*.xlsx);;CSV (*.csv)"
        )
        if path:
            self.output_path = path
            self.output_label.setText(path)

    def build_config(self, *, require_output: bool = True) -> WorkflowConfig:
        if self.files.count() == 0:
            raise ValueError("请先添加输入文件")
        if require_output and not self.output_path:
            raise ValueError("请选择输出文件")
        operations = [
            OperationConfig.model_validate_json(
                self.operations.item(i).data(Qt.ItemDataRole.UserRole)
            )
            for i in range(self.operations.count())
        ]
        mapping = {}
        if self.ecommerce_mode and self.files.count():
            from sheetflow.ecommerce import infer_mapping

            sample = read_table(self.files.item(0).text())
            mapping = infer_mapping([str(c) for c in sample.columns])
        return WorkflowConfig(
            version=1,
            input=InputConfig(paths=[self.files.item(i).text() for i in range(self.files.count())]),
            operations=operations,
            output=OutputConfig(path=self.output_path or "preview.xlsx"),
            mapping=mapping,
        )

    def load_preview(self) -> None:
        try:
            report = preview_workflow(self.build_config(require_output=False))
            frame = report.frame
            self.preview_hint.hide()
            self.preview.show()
            self.preview.setRowCount(len(frame))
            self.preview.setColumnCount(len(frame.columns))
            self.preview.setHorizontalHeaderLabels([str(c) for c in frame.columns])
            for row in range(len(frame)):
                for column in range(len(frame.columns)):
                    self.preview.setItem(row, column, QTableWidgetItem(str(frame.iat[row, column])))
            removed = report.before_rows - report.after_rows
            changed_columns = len(report.after_columns) - len(report.before_columns)
            self.status.setText(
                f"预览完成：{report.before_rows} → {report.after_rows} 行"
                f"（减少 {removed}），列数变化 {changed_columns:+d}"
            )
        except Exception as exc:
            QMessageBox.warning(self, "预览失败", str(exc))

    def save_config(self) -> None:
        try:
            config = self.build_config()
            path, _ = QFileDialog.getSaveFileName(
                self, "保存工作流", "workflow.yaml", "YAML (*.yaml *.yml)"
            )
            if path:
                save_workflow(config, path)
                self.status.setText(f"工作流已保存：{path}")
        except Exception as exc:
            QMessageBox.warning(self, "无法保存", str(exc))

    def load_config(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "打开工作流", "", "YAML (*.yaml *.yml)")
        if not path:
            return
        try:
            config = load_workflow(path)
            self.files.clear()
            self.operations.clear()
            for value in config.input.paths:
                self.files.addItem(value)
            for operation in config.operations:
                self.append_operation(json.dumps(operation.model_dump(), ensure_ascii=False))
            self.output_path = config.output.path
            self.output_label.setText(config.output.path)
        except SheetFlowError as exc:
            QMessageBox.warning(self, "无法打开", str(exc))

    def start_task(self) -> None:
        if self.worker and self.worker.isRunning():
            return
        try:
            config = self.build_config()
            if Path(config.output.path).exists():
                answer = QMessageBox.question(self, "确认覆盖", "输出文件已存在，是否覆盖？")
                if answer != QMessageBox.StandardButton.Yes:
                    return
                config.output.overwrite = True
            self.worker = Worker(config)
            self.worker.progress.connect(self.update_progress)
            self.worker.completed.connect(self.task_completed)
            self.worker.failed.connect(lambda text: QMessageBox.warning(self, "处理失败", text))
            self.worker.finished.connect(self.task_finished)
            self.run_button.setEnabled(False)
            self.cancel_button.setEnabled(True)
            self.progress_bar.setValue(0)
            self.worker.start()
        except Exception as exc:
            QMessageBox.warning(self, "无法开始", str(exc))

    def cancel_task(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.cancel_requested = True
            self.status.setText("正在安全取消……")

    def task_finished(self) -> None:
        self.run_button.setEnabled(True)
        self.cancel_button.setEnabled(False)

    def update_progress(self, value: int, text: str) -> None:
        self.progress_bar.setValue(value)
        self.status.setText(text)

    def task_completed(self, report: TaskReport) -> None:
        outputs = "\n".join(str(path) for path in report.output_paths)
        detail = f"输入文件：{report.input_count} 个\n最终订单：{report.rows} 行"
        if report.summary:
            detail += f"\n销售额：¥{report.summary.get('sales_amount', 0):,.2f}"
        QMessageBox.information(self, "处理完成", f"处理完成\n\n{detail}\n\n生成文件：\n{outputs}")


def main() -> None:
    application = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.show()
    application.exec()


if __name__ == "__main__":
    main()
