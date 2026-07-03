from PySide6.QtWidgets import (
    QWizard, QWizardPage, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QLabel, QComboBox, QSpinBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
    QMessageBox, QProgressBar, QPlainTextEdit, QTextEdit, QApplication, QGroupBox,
    QRadioButton, QButtonGroup, QSplitter, QWidget,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor, QBrush

from infrastructure.adapters.db_types import DBType
from infrastructure.adapters.adapter_factory import AdapterFactory
from domain import (
    ColumnInfo, TableInfo, SequenceInfo, TriggerInfo, ViewInfo, FullSchema,
    TypeConverter, DDLGenerator, MAPPING_REGISTRY,
)
from ui.dialogs import show_critical
from domain.migration.mapping_template import MappingTemplate


class SourcePage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Conexão de Origem")
        self.setSubTitle("Configure a conexão com o banco de dados de origem.")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(8)

        self._db_type = QComboBox()
        for value, label in DBType.choices():
            self._db_type.addItem(label, value)
        form.addRow("Tipo de Banco:", self._db_type)

        self._server = QLineEdit()
        self._server.setPlaceholderText("servidor ou IP")
        form.addRow("Servidor:", self._server)

        self._port = QSpinBox()
        self._port.setRange(0, 65535)
        self._port.setSpecialValueText("Auto")
        form.addRow("Porta:", self._port)

        self._database = QLineEdit()
        self._database.setPlaceholderText("nome do banco / DSN / caminho")
        form.addRow("Database:", self._database)

        self._username = QLineEdit()
        self._username.setPlaceholderText("usuário")
        form.addRow("Usuário:", self._username)

        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.Password)
        self._password.setPlaceholderText("senha")
        form.addRow("Senha:", self._password)

        layout.addLayout(form)

        self._test_btn = QPushButton("Testar Conexão")
        self._test_btn.clicked.connect(self._on_test)
        layout.addWidget(self._test_btn)

        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

    def _on_test(self):
        config = self._build_config()
        if not config:
            return
        adapter = AdapterFactory.create(config["type"])
        ok, error_msg = adapter.test_connection(self._to_connection_config(config))
        if ok:
            self._status_label.setText("Conexão OK")
            self._status_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            self._status_label.setText(f"Falha: {error_msg}")
            self._status_label.setStyleSheet("color: red; font-weight: bold;")

    def initializePage(self):
        src = self.wizard()._source_config
        if src:
            idx = self._db_type.findData(src.get("type", ""))
            if idx >= 0:
                self._db_type.setCurrentIndex(idx)
            if src.get("server"):
                self._server.setText(src["server"])
                self._server.setEnabled(False)
            if src.get("database"):
                self._database.setText(src["database"])
                self._database.setEnabled(False)
            if src.get("port"):
                self._port.setValue(src["port"])
            else:
                self._port.setValue(0)
            if src.get("username"):
                self._username.setText(src["username"])
            if src.get("password"):
                self._password.setText(src["password"])
            self._status_label.setText("✅ Pré-carregado da conexão atual")
            self._status_label.setStyleSheet("color: green; font-weight: bold;")

    def validatePage(self):
        self.wizard()._source_config = self._build_config()
        return True

    def _build_config(self) -> dict | None:
        return {
            "type": self._db_type.currentData(),
            "server": self._server.text().strip(),
            "port": self._port.value() or None,
            "database": self._database.text().strip(),
            "username": self._username.text().strip(),
            "password": self._password.text(),
            "use_windows_auth": False,
        }

    def _to_connection_config(self, cfg: dict):
        from domain.value_objects import ServerName, DatabaseName, ConnectionConfig
        return ConnectionConfig(
            db_type=cfg["type"],
            server=ServerName(cfg["server"] or cfg["database"]),
            database=DatabaseName(cfg["database"]),
            username=cfg["username"],
            password=cfg["password"],
            use_windows_auth=cfg.get("use_windows_auth", False),
            port=cfg["port"],
        )

    def get_config(self) -> dict:
        return self._build_config()


class TargetPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Conexão de Destino")
        self.setSubTitle("Configure a conexão com o banco de dados de destino.")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(8)

        self._db_type = QComboBox()
        for value, label in DBType.choices():
            self._db_type.addItem(label, value)
        self._db_type.setCurrentIndex(1)
        form.addRow("Tipo de Banco:", self._db_type)

        self._server = QLineEdit()
        self._server.setPlaceholderText("servidor ou IP")
        form.addRow("Servidor:", self._server)

        self._port = QSpinBox()
        self._port.setRange(0, 65535)
        self._port.setSpecialValueText("Auto")
        form.addRow("Porta:", self._port)

        self._database = QLineEdit()
        self._database.setPlaceholderText("ex.: postgres, template1")
        form.addRow("Database Conexão:", self._database)

        self._target_database = QLineEdit()
        self._target_database.setPlaceholderText("deixe em branco = mesmo da conexão")
        form.addRow("Database Destino:", self._target_database)

        self._create_db_cb = QCheckBox("Criar database destino se não existir")
        self._create_db_cb.setChecked(True)
        form.addRow("", self._create_db_cb)

        self._username = QLineEdit()
        self._username.setPlaceholderText("usuário")
        form.addRow("Usuário:", self._username)

        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.Password)
        self._password.setPlaceholderText("senha")
        form.addRow("Senha:", self._password)

        layout.addLayout(form)

        self._test_btn = QPushButton("Testar Conexão")
        self._test_btn.clicked.connect(self._on_test)
        layout.addWidget(self._test_btn)

        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

    def _on_test(self):
        config = self._build_config()
        if not config:
            return
        adapter = AdapterFactory.create(config["type"])
        ok, error_msg = adapter.test_connection(self._to_connection_config(config))
        if ok:
            self._status_label.setText("Conexão OK")
            self._status_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            self._status_label.setText(f"Falha: {error_msg}")
            self._status_label.setStyleSheet("color: red; font-weight: bold;")

    def validatePage(self):
        self.wizard()._target_config = self._build_config()
        return True

    def _build_config(self) -> dict | None:
        db = self._database.text().strip()
        tgt = self._target_database.text().strip() or db
        return {
            "type": self._db_type.currentData(),
            "server": self._server.text().strip(),
            "port": self._port.value() or None,
            "database": db,
            "target_database": tgt,
            "create_database": self._create_db_cb.isChecked(),
            "username": self._username.text().strip(),
            "password": self._password.text(),
            "use_windows_auth": False,
        }

    def _to_connection_config(self, cfg: dict):
        from domain.value_objects import ServerName, DatabaseName, ConnectionConfig
        return ConnectionConfig(
            db_type=cfg["type"],
            server=ServerName(cfg["server"] or cfg["database"]),
            database=DatabaseName(cfg["database"]),
            username=cfg["username"],
            password=cfg["password"],
            use_windows_auth=cfg.get("use_windows_auth", False),
            port=cfg["port"],
        )

    def get_config(self) -> dict:
        return self._build_config()


class ObjectSelectionPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Seleção de Objetos")
        self.setSubTitle("Selecione as tabelas, views e sequences para migrar.")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self._select_all = QPushButton("Selecionar Todos")
        self._deselect_all = QPushButton("Desmarcar Todos")
        btn_row = QHBoxLayout()
        btn_row.addWidget(self._select_all)
        btn_row.addWidget(self._deselect_all)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._tree = QTableWidget()
        self._tree.setColumnCount(3)
        self._tree.setHorizontalHeaderLabels(["", "Nome", "Tipo"])
        self._tree.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._tree.setSelectionMode(QTableWidget.NoSelection)
        layout.addWidget(self._tree, 1)

        self._summary = QLabel("Nenhum objeto carregado.")
        layout.addWidget(self._summary)

        self._items: list = []

        self._select_all.clicked.connect(self._on_select_all)
        self._deselect_all.clicked.connect(self._on_deselect_all)

    def initializePage(self):
        wizard = self.wizard()
        tables = getattr(wizard, "_schema_data", None)
        if not tables:
            src_cfg = wizard._source_config
            if not src_cfg:
                return
            adapter = AdapterFactory.create(src_cfg["type"])
            adapter.connect(wizard._to_conn_cfg(src_cfg))
            tables = adapter.get_schema()
            wizard._sequences = adapter.get_sequences()
            wizard._triggers = adapter.get_triggers()
            wizard._procedures = adapter.get_procedures()
            adapter.disconnect()

        self._tree.setRowCount(0)
        self._items = []
        for t in tables:
            row = self._tree.rowCount()
            self._tree.insertRow(row)
            cb = QTableWidgetItem()
            cb.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            cb.setCheckState(Qt.CheckState.Checked)
            self._tree.setItem(row, 0, cb)
            self._tree.setItem(row, 1, QTableWidgetItem(t.name))
            self._tree.setItem(row, 2, QTableWidgetItem(t.type))
            self._items.append(t)
        self._update_summary()

    def validatePage(self):
        wizard = self.wizard()
        wizard._selected_objects = self.get_selected()
        return True

    def _on_select_all(self):
        for row in range(self._tree.rowCount()):
            self._tree.item(row, 0).setCheckState(Qt.CheckState.Checked)
        self._update_summary()

    def _on_deselect_all(self):
        for row in range(self._tree.rowCount()):
            self._tree.item(row, 0).setCheckState(Qt.CheckState.Unchecked)
        self._update_summary()

    def _update_summary(self):
        total = self._tree.rowCount()
        sel = sum(1 for r in range(total) if self._tree.item(r, 0).checkState() == Qt.CheckState.Checked)
        self._summary.setText(f"{sel} de {total} objeto(s) selecionado(s).")

    def get_selected(self) -> dict:
        tables = []
        views = []
        sequences = []
        for row in range(self._tree.rowCount()):
            if self._tree.item(row, 0).checkState() != Qt.CheckState.Checked:
                continue
            t = self._items[row]
            if t.type == "VIEW":
                views.append(t)
            else:
                tables.append(t)
        return {"tables": tables, "views": views, "sequences": sequences}


class MappingReviewPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Revisão de Mapeamento")
        self.setSubTitle("Revise a conversão dos tipos entre origem e destino.")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self._table_combo = QComboBox()
        self._table_combo.currentIndexChanged.connect(self._on_table_changed)
        layout.addWidget(self._table_combo)

        template_btn_row = QHBoxLayout()
        self._save_template_btn = QPushButton("💾 Salvar Template...")
        self._save_template_btn.clicked.connect(self._on_save_template)
        self._load_template_btn = QPushButton("📂 Carregar Template...")
        self._load_template_btn.clicked.connect(self._on_load_template)
        template_btn_row.addWidget(self._save_template_btn)
        template_btn_row.addWidget(self._load_template_btn)
        template_btn_row.addStretch()
        layout.addLayout(template_btn_row)

        self._mapping_table = QTableWidget()
        self._mapping_table.setColumnCount(5)
        self._mapping_table.setHorizontalHeaderLabels(["Coluna", "Tipo Origem", "Tipo Destino", "DDL", "Alerta"])
        self._mapping_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._mapping_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._mapping_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._mapping_table.setAlternatingRowColors(True)
        layout.addWidget(self._mapping_table, 1)

        self._conflict_label = QLabel("")
        layout.addWidget(self._conflict_label)

    def _on_table_changed(self, idx):
        if idx < 0:
            return
        tname = self._table_combo.currentText()
        data = self._table_data.get(tname)
        if not data:
            return
        converted = data["converted"]
        self._mapping_table.setRowCount(len(converted))
        warn_brush = QBrush(QColor("#fff3cd"))

        for i, item in enumerate(converted):
            col = item["column"]
            mapping = item["mapping"]
            ddl = item["ddl_type"]
            has_conflict = item["has_conflict"]

            self._mapping_table.setItem(i, 0, QTableWidgetItem(col.name))
            self._mapping_table.setItem(i, 1, QTableWidgetItem(col.data_type))
            self._mapping_table.setItem(i, 2, QTableWidgetItem(mapping.target_type))
            self._mapping_table.setItem(i, 3, QTableWidgetItem(ddl))
            warn_text = mapping.warning or ""
            w_item = QTableWidgetItem(warn_text)
            if has_conflict:
                w_item.setBackground(warn_brush)
            self._mapping_table.setItem(i, 4, w_item)

        num_conflicts = len(data["conflicts"])
        if num_conflicts:
            self._conflict_label.setText(f"⚠ {num_conflicts} coluna(s) com alerta — revisar antes de continuar.")
            self._conflict_label.setStyleSheet("color: #856404; font-weight: bold; padding: 4px;")
        else:
            self._conflict_label.setText("✅ Todos os tipos mapeados sem conflitos.")
            self._conflict_label.setStyleSheet("color: green; font-weight: bold; padding: 4px;")

    def _on_save_template(self):
        wizard: QWizard = self.wizard()
        src_type = wizard._source_config["type"]
        tgt_type = wizard._target_config["type"]

        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "Salvar Template de Mapeamento", "template.json",
            "JSON Files (*.json);;All Files (*)"
        )
        if not path:
            return

        template = MappingTemplate.create(src_type, tgt_type)
        for tname, data in self._table_data.items():
            for item in data["converted"]:
                col = item["column"]
                mapping = item["mapping"]
                if item["has_conflict"]:
                    MappingTemplate.add_override(
                        template, tname, col.name, mapping.target_type
                    )
        MappingTemplate.save(template, path)

    def _on_load_template(self):
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        path, _ = QFileDialog.getOpenFileName(
            self, "Carregar Template de Mapeamento", "",
            "JSON Files (*.json);;All Files (*)"
        )
        if not path:
            return
        try:
            template = MappingTemplate.load(path)
        except Exception as e:
            QMessageBox.warning(self, "Erro", f"Falha ao carregar template: {e}")
            return

        wizard: QWizard = self.wizard()
        for tname, data in self._table_data.items():
            for item in data["converted"]:
                col = item["column"]
                source_type = col.data_type
                default_ddl = item["ddl_type"]
                new_ddl = MappingTemplate.apply_to_mapping(
                    template, tname, col.name, source_type, default_ddl
                )
                if new_ddl != default_ddl:
                    item["ddl_type"] = new_ddl
                    item["mapping"] = item["mapping"].__class__(
                        source_type=item["mapping"].source_type,
                        target_type=new_ddl,
                        warning=item["mapping"].warning,
                    )
                    item["has_conflict"] = False

        current_table = self._table_combo.currentText()
        if current_table:
            self._on_table_changed(self._table_combo.currentIndex())

    def initializePage(self):
        wizard = self.wizard()
        selected = wizard._selected_objects
        tables = selected.get("tables", [])
        src_type = wizard._source_config["type"]
        tgt_type = wizard._target_config["type"]

        wizard._type_converter = TypeConverter(src_type, tgt_type)
        wizard._ddl_generator = DDLGenerator(src_type, tgt_type)

        self._table_combo.clear()
        self._table_data = {}
        for t in tables:
            self._table_combo.addItem(t.name)
            converted = wizard._type_converter.convert_table(t)
            conflicts = [c for c in converted if c.get("has_conflict")]
            self._table_data[t.name] = {"table": t, "converted": converted, "conflicts": conflicts}
        self._template = MappingTemplate.create(src_type, tgt_type)


class ScriptPreviewPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Preview do Script")
        self.setSubTitle("Visualize o script DDL que será gerado para o banco de destino.")
        self._base_ddl = ""
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self._include_data_cb = QCheckBox("Incluir INSERTs dos dados no script")
        self._include_data_cb.setChecked(False)
        self._include_data_cb.toggled.connect(self._regenerate_script)
        layout.addWidget(self._include_data_cb)

        self._script_edit = QTextEdit()
        self._script_edit.setReadOnly(True)
        self._script_edit.setFont(QFont("Consolas", 10))
        self._script_edit.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e; color: #d4d4d4;
                border: 1px solid #333; padding: 6px;
            }
        """)
        layout.addWidget(self._script_edit, 1)

        btn_row = QHBoxLayout()
        self._copy_btn = QPushButton("📋 Copiar")
        self._copy_btn.clicked.connect(self._on_copy)
        self._save_btn = QPushButton("💾 Salvar .sql")
        self._save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(self._copy_btn)
        btn_row.addWidget(self._save_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def initializePage(self):
        wizard = self.wizard()
        selected = wizard._selected_objects
        src_type = wizard._source_config["type"]
        tgt_type = wizard._target_config["type"]

        tables = selected.get("tables", [])
        views = selected.get("views", [])
        sequences = wizard._sequences
        triggers = [t for t in wizard._triggers if t.table_name in {tb.name for tb in tables}]

        schema = FullSchema(
            tables=tables,
            views=views,
            sequences=sequences,
            triggers=triggers,
            procedures=wizard._procedures,
        )
        wizard._ddl_generator = DDLGenerator(src_type, tgt_type)
        self._base_ddl = wizard._ddl_generator.generate(schema)
        self._regenerate_script()

    def _on_copy(self):
        QApplication.clipboard().setText(self._script_edit.toPlainText())

    def _on_save(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "Salvar Script SQL", "migracao.sql", "SQL Files (*.sql);;All Files (*)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._script_edit.toPlainText())

    def _regenerate_script(self):
        wizard = self.wizard()
        if self._include_data_cb.isChecked():
            insert_block = self._fetch_and_generate_inserts()
            if insert_block:
                full = self._base_ddl + "\n\n" + insert_block
            else:
                full = self._base_ddl
            wizard._generated_script = full
            wizard._has_data_scripts = bool(insert_block)
            self._script_edit.setPlainText(full)
        else:
            wizard._generated_script = self._base_ddl
            wizard._has_data_scripts = False
            self._script_edit.setPlainText(self._base_ddl)

    def _fetch_and_generate_inserts(self):
        wizard = self.wizard()
        src_cfg = wizard._source_config
        tgt_type = wizard._target_config["type"] if wizard._target_config else "postgresql"
        tables = wizard._selected_objects.get("tables", [])
        if not tables:
            return ""

        try:
            adapter = AdapterFactory.create(src_cfg["type"])
            adapter.connect(wizard._to_conn_cfg(src_cfg))
        except Exception as e:
            return f"\n-- Erro ao conectar na origem para gerar INSERTs: {e}\n"

        all_inserts = []
        for t in tables:
            tname = t.name
            try:
                from domain.value_objects import SQLText as ST
                result = adapter.execute(ST(f"SELECT * FROM {tname}"))
                if result.success and result.rows:
                    stmts = self._generate_inserts(tname, result.columns, result.rows, db_type=tgt_type)
                    all_inserts.append(f"-- Dados da tabela: {tname}")
                    all_inserts.extend(stmts)
                else:
                    all_inserts.append(f"-- Tabela {tname}: sem dados")
            except Exception as e:
                all_inserts.append(f"-- Tabela {tname}: erro ao buscar dados → {e}")

        adapter.disconnect()
        return "\n".join(all_inserts)

    @staticmethod
    def _format_sql_value(val):
        if val is None:
            return "NULL"
        if isinstance(val, bool):
            return "TRUE" if val else "FALSE"
        if isinstance(val, (int, float)):
            return str(val)
        s = str(val)
        s = s.replace("'", "''")
        return f"'{s}'"

    @staticmethod
    def _qi(name: str, db_type: str) -> str:
        q = "`" if db_type in ("mysql", "mariadb") else '"'
        return f"{q}{name}{q}"

    @staticmethod
    def _generate_inserts(tname, columns, rows, db_type="postgresql", batch_size=500):
        stmts = []
        q = "`" if db_type in ("mysql", "mariadb") else '"'
        q_tname = f"{q}{tname}{q}"
        col_list = ", ".join(f"{q}{c}{q}" for c in columns)
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            values_list = ", ".join(
                "(" + ", ".join(ScriptPreviewPage._format_sql_value(val) for val in row) + ")"
                for row in batch
            )
            stmts.append(f'INSERT INTO {q_tname} ({col_list}) VALUES {values_list};')
        return stmts


class ExecutionPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Executar Migração")
        self.setSubTitle("Execute a migração no banco de destino.")
        self._items: list = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self._continue_on_error = QCheckBox("Continuar mesmo em caso de erro")
        self._continue_on_error.setChecked(True)
        layout.addWidget(self._continue_on_error)

        self._execute_btn = QPushButton("▶ Executar Migração")
        self._execute_btn.setStyleSheet("""
            QPushButton {
                background-color: #107c10; color: white; padding: 10px 30px;
                font-weight: bold; font-size: 13px; border-radius: 4px;
            }
            QPushButton:hover { background-color: #0b6b0b; }
            QPushButton:disabled { background-color: #ccc; }
        """)
        self._execute_btn.clicked.connect(self._on_execute)
        layout.addWidget(self._execute_btn)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setFont(QFont("Consolas", 10))
        self._log.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e; color: #d4d4d4;
                border: 1px solid #333; padding: 6px;
            }
        """)
        layout.addWidget(self._log, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._new_btn = QPushButton("🔄 Nova Migração")
        self._new_btn.setVisible(False)
        self._new_btn.clicked.connect(self._on_new)
        self._close_btn = QPushButton("✅ Fechar")
        self._close_btn.setVisible(False)
        self._close_btn.clicked.connect(self._on_close)
        btn_row.addWidget(self._new_btn)
        btn_row.addWidget(self._close_btn)
        layout.addLayout(btn_row)

    def initializePage(self):
        import re
        wizard: QWizard = self.wizard()
        self._src_cfg = wizard._source_config
        self._tgt_cfg = wizard._target_config
        script = wizard._generated_script
        clean = re.sub(r'^--.*$', '', script, flags=re.MULTILINE)
        statements = [s.strip() for s in clean.split(";") if s.strip()]
        self._statements = statements
        self._has_data_scripts = getattr(wizard, '_has_data_scripts', False)
        self._log.clear()
        self._execute_btn.setEnabled(True)
        self._new_btn.setVisible(False)
        self._close_btn.setVisible(False)

    def _append_log(self, text: str):
        self._log.appendPlainText(text)
        QApplication.processEvents()

    def _on_execute(self):
        wizard: QWizard = self.wizard()
        src_cfg = self._src_cfg
        tgt_cfg_raw = self._tgt_cfg
        statements = self._statements

        tgt_cfg = dict(tgt_cfg_raw)
        target_db = tgt_cfg.get("target_database", "") or tgt_cfg["database"]
        create_db = tgt_cfg.get("create_database", False)

        src_adapter = AdapterFactory.create(src_cfg["type"])
        tgt_adapter = AdapterFactory.create(tgt_cfg["type"])

        from infrastructure.migration_logger import MigrationLogger
        log = MigrationLogger()

        # Phase 0: Create target database if needed
        if create_db and target_db != tgt_cfg["database"]:
            self._append_log("─" * 40)
            self._append_log("Fase 0: Preparando database destino...")
            try:
                tgt_adapter.connect(wizard._to_conn_cfg(tgt_cfg))
                from domain.value_objects import SQLText as ST
                db_type = tgt_cfg["type"]
                if db_type == "postgresql":
                    sql = f'CREATE DATABASE "{target_db}"'
                elif db_type in ("mariadb", "mysql"):
                    sql = f"CREATE DATABASE IF NOT EXISTS `{target_db}`"
                elif db_type == "sqlite":
                    sql = None  # SQLite is file-based, no CREATE DATABASE
                else:
                    sql = None
                if sql:
                    result = tgt_adapter.execute_autocommit(ST(sql))
                    if result.success:
                        self._append_log(f"  ✅ Database '{target_db}' criado/verificado")
                    else:
                        msg = result.message.lower()
                        if "already exists" in msg:
                            self._append_log(f"  ℹ Database '{target_db}' já existe")
                        else:
                            self._append_log(f"  ⚠ {result.message[:100]}")
                tgt_adapter.disconnect()
            except Exception as e:
                msg = str(e).lower()
                if "already exists" in msg:
                    self._append_log(f"  ℹ Database '{target_db}' já existe")
                else:
                    self._append_log(f"  ⚠ Erro ao criar database: {str(e)[:100]}")
            tgt_cfg["database"] = target_db

        try:
            tgt_adapter.connect(wizard._to_conn_cfg(tgt_cfg))
        except Exception as e:
            self._append_log(f"❌ Erro ao conectar no destino: {e}")
            return

        try:
            src_adapter.connect(wizard._to_conn_cfg(src_cfg))
        except Exception as e:
            self._append_log(f"⚠ Falha ao reconectar na origem para copiar dados: {e}")
            src_adapter = None

        self._execute_btn.setEnabled(False)
        self._progress.setVisible(True)
        QApplication.processEvents()

        log.log_migration_start(f"{src_cfg['type']}:{src_cfg['server']}", f"{tgt_cfg['type']}:{tgt_cfg['server']}")

        self._progress.setMaximum(len(statements) + 2)
        self._progress.setValue(0)
        ok = 0
        fail = 0

        # Phase 1: DDL
        self._append_log("─" * 40)
        self._append_log("Fase 1: Executando DDL...")
        for i, stmt in enumerate(statements):
            try:
                from domain.value_objects import SQLText
                result = tgt_adapter.execute(SQLText(stmt))
                if result.success:
                    ok += 1
                    self._append_log(f"  ✅ {stmt[:80]}...")
                else:
                    fail += 1
                    self._append_log(f"  ❌ {stmt[:80]}... → {result.message[:100]}")
                    if not self._continue_on_error.isChecked():
                        break
            except Exception as e:
                fail += 1
                self._append_log(f"  ❌ {stmt[:80]}... → {e}")
                if not self._continue_on_error.isChecked():
                    break
            self._progress.setValue(i + 1)
            QApplication.processEvents()

        # Phase 2: Data migration
        self._append_log("─" * 40)
        data_ok = 0
        data_fail = 0

        if not self._has_data_scripts:
            self._append_log("Fase 2: Copiando dados...")
            selected = wizard._selected_objects
            tables = selected.get("tables", [])
            tgt_db_type = tgt_cfg.get("type", "postgresql")
            tgt_q = "`" if tgt_db_type in ("mysql", "mariadb") else '"'

            if src_adapter is not None:
                for t in tables:
                    tname = t.name
                    try:
                        from domain.value_objects import SQLText as ST
                        src_q = "`" if src_cfg.get("type") in ("mysql", "mariadb") else '"'
                        q_tname_src = f"{src_q}{tname}{src_q}"
                        result = src_adapter.execute(ST(f"SELECT * FROM {q_tname_src}"))
                        if result.success and result.rows:
                            rows = result.rows
                            cols = result.columns
                            if tgt_db_type in ("mssql", "firebird", "sqlite"):
                                placeholders = ", ".join(["?"] * len(cols))
                            elif tgt_db_type == "oracle":
                                placeholders = ", ".join(f":{i+1}" for i in range(len(cols)))
                            else:
                                placeholders = ", ".join(["%s"] * len(cols))
                            q_tname = f"{tgt_q}{tname}{tgt_q}"
                            col_names = ", ".join(f"{tgt_q}{c}{tgt_q}" for c in cols)
                            tgt_sql = f"INSERT INTO {q_tname} ({col_names}) VALUES ({placeholders})"
                            batch_size = 500
                            total = len(rows)
                            ins_ok = 0
                            ins_fail = 0
                            for start in range(0, total, batch_size):
                                chunk = rows[start:start + batch_size]
                                try:
                                    r = tgt_adapter.executemany(tgt_sql, chunk)
                                    ins_ok += r.rows_affected
                                except Exception:
                                    ins_fail += len(chunk)
                            log.log(tname, "TABLE", "DATA COPY", "OK" if ins_fail == 0 else "PARTIAL",
                                    f"{ins_ok} rows inserted, {ins_fail} errors")
                            self._append_log(f"  {'✅' if ins_fail == 0 else '⚠'} {tname}: {ins_ok} linha(s) copiada(s)")
                            data_ok += ins_ok
                            data_fail += ins_fail
                        else:
                            self._append_log(f"  ⚠ {tname}: tabela vazia ou sem dados")
                    except Exception as e:
                        data_fail += 1
                        self._append_log(f"  ❌ {tname}: erro ao copiar dados → {e}")
                    self._progress.setValue(len(statements) + 1)
                    QApplication.processEvents()
            else:
                self._append_log("  ⚠ Reconexão com origem falhou — dados não copiados")
        else:
            self._append_log("  ℹ INSERTs já incluídos no script — fase de dados pulada")

        if src_adapter:
            src_adapter.disconnect()
        tgt_adapter.disconnect()

        self._progress.setValue(self._progress.maximum())
        log.log_migration_end(ok + data_ok, fail + data_fail)

        if self._has_data_scripts:
            data_line = "Dados: incluídos no script (INSERTs)"
        else:
            data_line = f"Dados: {data_ok} linha(s) inseridas, {data_fail} erro(s)"

        summary = f"\n{'='*40}\nMigração concluída!\nDDL: {ok} OK, {fail} falha(s)\n{data_line}\n{'='*40}"
        self._append_log(summary)

        self._new_btn.setVisible(True)
        self._close_btn.setVisible(True)

    def _on_new(self):
        self._new_btn.setVisible(False)
        self._close_btn.setVisible(False)
        self._execute_btn.setEnabled(True)
        self._log.clear()
        self._progress.setVisible(False)

    def _on_close(self):
        wizard: QWizard = self.wizard()
        wizard.accept()


class MigrationDialog(QWizard):
    def __init__(self, parent=None, source_info: dict | None = None,
                 schema_data: list | None = None):
        super().__init__(parent)
        self.setWindowTitle("Migrar Banco de Dados")
        self.setMinimumSize(800, 600)
        self.resize(950, 680)
        self.setWizardStyle(QWizard.ModernStyle)

        self._source_config = source_info
        self._schema_data = schema_data or []
        self._target_config = None
        self._selected_objects = {}
        self._type_converter = None
        self._ddl_generator = None
        self._generated_script = ""
        self._sequences: list[SequenceInfo] = []
        self._triggers: list[TriggerInfo] = []
        self._procedures: list[ProcedureInfo] = []

        self.addPage(SourcePage(self))
        self.addPage(TargetPage(self))
        self.addPage(ObjectSelectionPage(self))
        self.addPage(MappingReviewPage(self))
        self.addPage(ScriptPreviewPage(self))
        self.addPage(ExecutionPage(self))

    @staticmethod
    def _to_conn_cfg(cfg: dict):
        from domain.value_objects import ServerName, DatabaseName, ConnectionConfig
        return ConnectionConfig(
            db_type=cfg["type"],
            server=ServerName(cfg["server"] or cfg["database"]),
            database=DatabaseName(cfg["database"]),
            username=cfg["username"],
            password=cfg["password"],
            use_windows_auth=cfg.get("use_windows_auth", False),
            port=cfg["port"],
        )

    def accept(self):
        super().accept()

    def reject(self):
        super().reject()
