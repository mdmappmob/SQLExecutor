# Changelog

## 2026-06-18 — Edição inline, Paste, Paginação, Comentários, Importação resiliente

### `infrastructure/mssql_adapter.py`
- **executemany** agora faz `commit()` por linha e `rollback()` + continua em caso de erro, em vez de falhar o lote inteiro (resolvia ~45% de carga em `lancamento_contabil_item`).

### `ui/import_dialog.py`
- Contagem de importados agora usa `result.rows_affected` real.
- Exibe o primeiro erro no `QMessageBox.warning` quando há falhas.

### `infrastructure/i18n.py`
- Novas chaves em `result_panel`: `save_changes`, `tab_editable`, `no_changes`, `save_confirm_title`, `save_confirm_text`, `save_ok`, `save_error`, `save_partial`, `paste_done`, `edit_not_available`.

### `ui/result_panel.py`
- **Paginação client‑side**: barra com Primeira/←/→/Última + combo "Por página:" (50–1000). Todas as linhas ficam em memória, mas só a página atual é renderizada no `QTableWidget`.
- **Edição inline**: `show_results()` aceita `editable=True/False` + `table_name`.
- **Botão "Salvar Alterações"**: agrupa células alteradas por linha, gera `UPDATE` (linhas existentes) ou `INSERT` (linhas novas). Fundo amarelo (`#fff3cd`) em células modificadas.
- **_EditableTable**: subclasse de `QTableWidget` que intercepta `Ctrl+V` e parseia TSV da área de transferência, colando múltiplas linhas/colunas.
- **_fetch_column_types()**: consulta `INFORMATION_SCHEMA.COLUMNS` para mapear nome→tipo.
- **_convert_save_value()**: converte strings para `date`/`datetime`/`int`/`float` conforme o tipo da coluna, evitando erro ODBC 241 (conversão de data).
- **Linha em branco**: quando `editable=True` e SELECT retorna 0 linhas, uma linha em branco é adicionada para permitir clique + paste.
- **Mensagens**: resultado do Save é registrado na aba "Mensagens" com timestamp.
- **Sinal `status_message`**: emitido para a barra de status da MainWindow após Save/Export.
- **Botões**: `Salvar` e `Exportar` realocados para o `btn_layout` do `SQLEditor` via `add_left_button()`. Exportar ganhou cor teal (`#17a2b8`), Salvar padding uniformizado.

### `ui/sql_editor.py`
- **`strip_sql_comments()`**: função que remove `--` até fim da linha e `/*...*/` (multilinha).
- **`get_sql()`**: se houver seleção no editor, retorna só o texto selecionado; senão, retorna o texto completo. Ambos passam por `strip_sql_comments()`.
- **`_SQLCommentHighlighter`**: `QSyntaxHighlighter` que aplica itálico em `--` e `/*...*/` (com suporte a comentários multilinha via `previousBlockState`).
- **`add_left_button(btn)`**: insere widgets no `_btn_layout` antes do `stretch`, permitindo que botões externos (Salvar, Exportar) compartilhem a mesma fileira.

### `ui/main_window.py`
- **`_is_single_table_select(sql)`**: detecta se o SQL é `SELECT` de tabela única (rejeita `JOIN`, `UNION`, `INTERSECT`, `EXCEPT`, `APPLY`, subqueries) e extrai o nome da tabela (com schema).
- **`_on_execute()`**: passa `editable=True` + `table_name` para `show_results()` quando aplicável.
- **`_build_ui()`**: chama `sql_editor.add_left_button()` para inserir `save_btn` e `export_btn` no mesmo layout do editor.
- Conecta `result_panel.status_message` à `status_bar.showMessage`.
