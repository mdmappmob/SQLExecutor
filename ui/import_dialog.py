from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QLabel, QLineEdit, QTableWidget,
    QTableWidgetItem, QFileDialog, QCheckBox,
    QMessageBox, QSpinBox, QHeaderView, QComboBox,
    QGroupBox, QProgressBar, QApplication,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

from infrastructure.csv_parser import CsvParser, CsvProfile, BatchInsert
from infrastructure.i18n import I18N


class ImportDialog(QDialog):
    def __init__(self, adapter, parent=None):
        super().__init__(parent)
        self.setWindowTitle(I18N.import_dialog["title"])
        self.setMinimumSize(750, 550)
        self.resize(850, 600)

        self._adapter = adapter
        self._profile: CsvProfile | None = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        file_layout = QHBoxLayout()
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText(I18N.import_dialog["file_ph"])
        self.file_path_edit.setReadOnly(True)
        browse_btn = QPushButton(I18N.import_dialog["browse"])
        browse_btn.clicked.connect(self._browse)
        file_layout.addWidget(self.file_path_edit, 1)
        file_layout.addWidget(browse_btn)
        layout.addLayout(file_layout)

        options_layout = QHBoxLayout()
        self.header_cb = QCheckBox(I18N.import_dialog["header_cb"])
        self.header_cb.setChecked(True)
        self.header_cb.toggled.connect(self._reprofile)

        self.delimiter_combo = QComboBox()
        self.delimiter_combo.addItems([
            I18N.import_dialog["delimiter_auto"],
            I18N.import_dialog["delimiter_comma"],
            I18N.import_dialog["delimiter_semicolon"],
            I18N.import_dialog["delimiter_tab"],
            I18N.import_dialog["delimiter_pipe"],
        ])
        self.delimiter_combo.currentIndexChanged.connect(self._reprofile)

        options_layout.addWidget(self.header_cb)
        options_layout.addSpacing(20)
        options_layout.addWidget(QLabel(I18N.import_dialog["delimiter_label"]))
        options_layout.addWidget(self.delimiter_combo)
        options_layout.addStretch()
        layout.addLayout(options_layout)

        table_group = QGroupBox(I18N.import_dialog["preview_group"])
        table_layout = QVBoxLayout(table_group)
        self.preview_table = QTableWidget()
        self.preview_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.setFont(QFont("Consolas", 9))
        table_layout.addWidget(self.preview_table)
        layout.addWidget(table_group, 1)

        mapping_group = QGroupBox(I18N.import_dialog["mapping_group"])
        mapping_layout = QVBoxLayout(mapping_group)

        table_name_layout = QHBoxLayout()
        self.table_name_edit = QLineEdit()
        self.table_name_edit.setPlaceholderText(I18N.import_dialog["table_ph"])
        table_name_layout.addWidget(self.table_name_edit, 1)
        self.fetch_btn = QPushButton(I18N.import_dialog["fetch_btn"])
        self.fetch_btn.setToolTip(I18N.import_dialog["fetch_tooltip"])
        self.fetch_btn.setEnabled(False)
        self.fetch_btn.clicked.connect(self._fetch_columns)
        self.table_name_edit.textChanged.connect(self._update_fetch_btn)
        table_name_layout.addWidget(self.fetch_btn)
        mapping_layout.addLayout(table_name_layout)

        self.mapping_table = QTableWidget()
        self.mapping_table.setColumnCount(2)
        self.mapping_table.setHorizontalHeaderLabels([I18N.import_dialog["source_column"], I18N.import_dialog["target_column"]])
        self.mapping_table.horizontalHeader().setStretchLastSection(True)
        self.mapping_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        mapping_layout.addWidget(self.mapping_table, 1)

        batch_layout = QHBoxLayout()
        self.mapping_info = QLabel("")
        self.mapping_info.setStyleSheet("color: #888;")
        batch_layout.addWidget(self.mapping_info, 1)
        batch_layout.addWidget(QLabel(I18N.import_dialog["batch_label"]))
        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setRange(100, 10000)
        self.batch_size_spin.setValue(1000)
        self.batch_size_spin.setSuffix(I18N.import_dialog["batch_suffix"])
        batch_layout.addWidget(self.batch_size_spin)
        mapping_layout.addLayout(batch_layout)

        layout.addWidget(mapping_group)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        btn_layout = QHBoxLayout()
        self.import_btn = QPushButton(I18N.import_dialog["import_btn"])
        self.import_btn.setEnabled(False)
        self.import_btn.setStyleSheet("""
            QPushButton {
                background-color: #107c10; color: white; padding: 8px 30px;
                font-weight: bold; font-size: 12px; border-radius: 4px;
            }
            QPushButton:hover { background-color: #0b6b0b; }
            QPushButton:disabled { background-color: #ccc; }
        """)
        self.import_btn.clicked.connect(self._import)
        cancel_btn = QPushButton(I18N.import_dialog["cancel_btn"])
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(self.import_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _detect_delimiter_from_combo(self) -> str | None:
        idx = self.delimiter_combo.currentIndex()
        mapping = {0: None, 1: ",", 2: ";", 3: "\t", 4: "|"}
        return mapping.get(idx)

    def _get_encoding(self) -> str:
        return "utf-8-sig"

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, I18N.import_dialog["title"], "", "CSV Files (*.csv *.txt);;All Files (*)"
        )
        if path:
            self.file_path_edit.setText(path)
            self._reprofile()

    def _reprofile(self):
        path = self.file_path_edit.text()
        if not path:
            return

        try:
            profile = CsvParser.profile(
                path,
                has_header=self.header_cb.isChecked(),
                encoding=self._get_encoding(),
            )

            delimiter = self._detect_delimiter_from_combo()
            if delimiter is not None:
                profile.delimiter = delimiter

            self._profile = profile
            self._show_preview(profile)
            self._update_mapping_info(profile)
            self.import_btn.setEnabled(True)
        except Exception as e:
            self._profile = None
            self.preview_table.setColumnCount(0)
            self.preview_table.setRowCount(0)
            self.mapping_info.setText(I18N.main_window["unexpected_error"] + f": {e}")
            self.mapping_info.setStyleSheet("color: #d32f2f;")
            self.import_btn.setEnabled(False)

    def _update_fetch_btn(self):
        has_table = bool(self.table_name_edit.text().strip())
        has_profile = self._profile is not None
        has_connection = self._adapter.is_connected()
        self.fetch_btn.setEnabled(has_table and has_profile and has_connection)

    def _fetch_columns(self):
        table = self.table_name_edit.text().strip()
        if not table:
            return
        try:
            cols = self._adapter.get_table_columns(table)
            if not cols:
                QMessageBox.warning(
                    self, I18N.result_panel["export_error"],
                    I18N.import_dialog["fetch_error"].format(msg="Tabela não encontrada ou sem colunas")
                )
                return
            db_cols = [c.name for c in cols]
            row_count = min(len(db_cols), self.mapping_table.rowCount())
            for i in range(row_count):
                item = self.mapping_table.item(i, 1)
                if item:
                    item.setText(db_cols[i])
            if len(db_cols) > len(self._profile.columns):
                QMessageBox.information(
                    self, I18N.import_dialog["fetch_btn"],
                    I18N.import_dialog["fetch_partial_less"].format(db=len(db_cols), csv=len(self._profile.columns))
                )
            elif len(db_cols) < len(self._profile.columns):
                QMessageBox.information(
                    self, I18N.import_dialog["fetch_btn"],
                    I18N.import_dialog["fetch_partial_more"].format(db=len(db_cols), csv=len(self._profile.columns), n=len(db_cols))
                )
            else:
                self.mapping_info.setText(I18N.import_dialog["fetch_ok"].format(table=table, n=len(db_cols)))
        except Exception as e:
            QMessageBox.critical(self, I18N.import_dialog["fetch_btn"], I18N.import_dialog["fetch_critical"].format(error=e))

    def _show_preview(self, profile: CsvProfile):
        display_cols = [
            I18N.import_dialog["column_display"].format(n=c) if c.isdigit() else c
            for c in profile.columns
        ]
        self.preview_table.setColumnCount(len(profile.columns))
        self.preview_table.setHorizontalHeaderLabels(display_cols)
        self.preview_table.setRowCount(len(profile.sample_rows))

        for r, row in enumerate(profile.sample_rows):
            for c, val in enumerate(row):
                item = QTableWidgetItem(val)
                item.setFont(QFont("Consolas", 9))
                self.preview_table.setItem(r, c, item)

        self.preview_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.preview_table.verticalHeader().setVisible(False)

        self.mapping_table.setRowCount(len(profile.columns))
        for i, src in enumerate(profile.columns):
            display = I18N.import_dialog["column_display"].format(n=src) if src.isdigit() else src
            src_item = QTableWidgetItem(display)
            src_item.setFlags(src_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.mapping_table.setItem(i, 0, src_item)
            tgt_item = QTableWidgetItem(src)
            self.mapping_table.setItem(i, 1, tgt_item)

    def _update_mapping_info(self, profile: CsvProfile):
        cols = profile.columns[:6]
        suffix = ", ..." if len(profile.columns) > 6 else ""
        info = I18N.import_dialog["detected_info"].format(n=profile.total_rows, cols=len(profile.columns))
        self.mapping_info.setText(info)
        self.mapping_info.setStyleSheet("color: #333;")

    def _import(self):
        if not self._profile:
            return

        table = self.table_name_edit.text().strip()
        if not table:
            QMessageBox.warning(self, I18N.main_window["validation_title"], I18N.import_dialog["validation_table"])
            return

        if not self._adapter.is_connected():
            QMessageBox.warning(self, I18N.main_window["validation_title"], I18N.import_dialog["not_connected"])
            return

        delimiter = self._detect_delimiter_from_combo() or self._profile.delimiter

        column_mapping = {}
        for i in range(self.mapping_table.rowCount()):
            src = self.mapping_table.item(i, 0).text()
            tgt = self.mapping_table.item(i, 1).text().strip()
            if tgt:
                column_mapping[self._profile.columns[i]] = tgt

        if not column_mapping:
            QMessageBox.warning(self, I18N.main_window["validation_title"], I18N.import_dialog["validation_columns"])
            return

        try:
            batch = CsvParser.prepare_insert(
                self._profile.file_path,
                table,
                column_mapping,
                has_header=self.header_cb.isChecked(),
                encoding=self._get_encoding(),
                batch_size=self.batch_size_spin.value(),
            )
        except Exception as e:
            QMessageBox.critical(self, I18N.import_dialog["parse_error"], str(e))
            return

        total = len(batch.params)
        if total == 0:
            QMessageBox.information(self, I18N.import_dialog["import_btn"], I18N.import_dialog["no_data"])
            return

        reply = QMessageBox.question(
            self, I18N.import_dialog["confirm_title"],
            I18N.import_dialog["confirm_text"].format(n=total, table=table, cols=", ".join(column_mapping.values())),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.No:
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(0)
        self.import_btn.setEnabled(False)
        QApplication.processEvents()

        batch_size = self.batch_size_spin.value()
        imported = 0
        errors = 0
        last_error = ""

        for start in range(0, total, batch_size):
            chunk = batch.params[start:start + batch_size]
            result = self._adapter.executemany(batch.sql_template, chunk)
            imported += result.rows_affected
            failed_count = len(chunk) - result.rows_affected
            errors += failed_count
            if failed_count > 0 and not last_error:
                last_error = result.message
            self.progress_bar.setValue(min(start + batch_size, total))
            QApplication.processEvents()

        self.progress_bar.setVisible(False)
        self.import_btn.setEnabled(True)

        if errors == 0:
            QMessageBox.information(
                self, I18N.import_dialog["import_complete_title"],
                I18N.import_dialog["import_complete_text"].format(n=imported, table=table)
            )
            self.accept()
        else:
            msg = I18N.import_dialog["import_errors_text"].format(ok=imported, erros=errors)
            if last_error:
                msg += f"\n\nDetalhes:\n{last_error}"
            QMessageBox.warning(
                self, I18N.import_dialog["import_errors_title"],
                msg
            )
            self.accept()
