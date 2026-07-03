from datetime import datetime

from domain.entities import SequenceInfo, TriggerInfo, ViewInfo, FullSchema, ProcedureInfo
from domain.interfaces import ColumnInfo, ForeignKeyInfo, IndexInfo, TableInfo
from domain.migration.type_converter import TypeConverter


class DDLGenerator:
    def __init__(self, source_db_type: str, target_db_type: str):
        self._converter = TypeConverter(source_db_type, target_db_type)
        self.source = source_db_type
        self.target = target_db_type

    def generate(self, schema: FullSchema) -> str:
        parts = []
        parts.append(self._header())
        if schema.sequences:
            parts.append(self._generate_sequences(schema.sequences))
        if schema.tables:
            parts.append(self._generate_tables(schema.tables))
        if schema.views:
            parts.append(self._generate_views(schema.views))
        if schema.triggers:
            parts.append(self._generate_triggers(schema.triggers))
        if schema.procedures:
            parts.append(self._generate_procedures(schema.procedures))
        return '\n\n'.join(filter(None, parts))

    def _header(self) -> str:
        now = datetime.now().strftime('%d/%m/%Y %H:%M')
        return (
            f'-- =============================================\n'
            f'-- Script de Migracao: {self.source} -> {self.target}\n'
            f'-- Gerado em: {now}\n'
            f'-- ============================================='
        )

    def _generate_sequences(self, sequences: list[SequenceInfo]) -> str:
        lines = ['-- Sequences']
        for seq in sequences:
            name = self._quote(seq.name)
            if self.target in ('mysql', 'mariadb', 'sqlite'):
                lines.append(f'-- Sequence {name} — MySQL/MariaDB não suporta CREATE SEQUENCE')
                lines.append(f'-- Use AUTO_INCREMENT na tabela ou adapte manualmente')
                continue
            if self.target == 'mssql':
                stmt = f'CREATE SEQUENCE {name}'
            else:
                stmt = f'CREATE SEQUENCE IF NOT EXISTS {name}'
            parts = [f'  START WITH {seq.start_value}']
            if seq.increment != 1:
                parts.append(f'  INCREMENT BY {seq.increment}')
            if seq.min_value is not None:
                parts.append(f'  MINVALUE {seq.min_value}')
            if seq.max_value is not None:
                parts.append(f'  MAXVALUE {seq.max_value}')
            stmt += '\n' + '\n'.join(parts) + ';'
            lines.append(stmt)
        return '\n\n'.join(lines)

    def _topological_sort(self, tables: list[TableInfo]) -> list[TableInfo]:
        table_map = {t.name: t for t in tables}
        dependents: dict[str, set[str]] = {}
        for t in tables:
            refs = set()
            for fk in t.foreign_keys:
                if fk.ref_table in table_map:
                    refs.add(fk.ref_table)
            dependents[t.name] = refs

        in_degree = {name: len(refs) for name, refs in dependents.items()}
        queue = [name for name, deg in in_degree.items() if deg == 0]
        sorted_names = []

        while queue:
            name = queue.pop(0)
            sorted_names.append(name)
            for tname, refs in dependents.items():
                if name in refs:
                    in_degree[tname] -= 1
                    if in_degree[tname] == 0 and tname not in sorted_names:
                        queue.append(tname)

        remaining = [t for t in tables if t.name not in sorted_names]
        result = [table_map[n] for n in sorted_names] + remaining
        return result

    def _generate_tables(self, tables: list[TableInfo]) -> str:
        sections = []
        sorted_tables = self._topological_sort(tables)
        for table in sorted_tables:
            if table.type != 'TABLE':
                continue
            sections.append(self._generate_table(table))
        if not sections:
            return ''
        return '\n\n'.join(sections)

    def _generate_table(self, table: TableInfo) -> str:
        tname = self._quote(table.name)
        converted = self._converter.convert_table(table)

        col_lines = []
        pk_cols: list[str] = []
        fk_lines: list[str] = []
        check_lines: list[str] = []

        for item in converted:
            col = item['column']
            mapping = item['mapping']
            ddl_type = item['ddl_type']
            cname = self._quote(col.name)
            parts = [f'  {cname} {ddl_type}']
            if not col.nullable:
                parts.append('NOT NULL')
            if col.default_value:
                dv = col.default_value.strip()
                if dv.upper() != 'NULL':
                    if dv.upper().startswith('DEFAULT'):
                        parts.append(dv)
                    else:
                        parts.append(f'DEFAULT {dv}')
            if col.is_pk:
                pk_cols.append(cname)
            if col.check_constraint:
                check_lines.append(f'  CONSTRAINT {self._quote("chk_" + col.name)} CHECK ({col.check_constraint})')
            col_lines.append(' '.join(parts))

        if pk_cols:
            col_lines.append(f'  PRIMARY KEY ({", ".join(pk_cols)})')

        col_lines.extend(check_lines)

        for fk in table.foreign_keys:
            fk_lines.append(
                f'  CONSTRAINT {self._quote(fk.fk_name or f"fk_{table.name}_{fk.column}")} '
                f'FOREIGN KEY ({self._quote(fk.column)}) '
                f'REFERENCES {self._quote(fk.ref_table)}({self._quote(fk.ref_column)})'
            )
        col_lines.extend(fk_lines)

        cols_sql = ',\n'.join(col_lines)

        lines = [f'-- Tabela: {table.name}', f'CREATE TABLE {tname} (']
        lines.append(cols_sql)
        lines.append(');')

        for idx in table.indexes:
            idx_name = self._quote(idx.name)
            idx_cols = ', '.join(self._quote(c) for c in idx.columns)
            unique = 'UNIQUE ' if idx.is_unique else ''
            lines.append(f'CREATE {unique}INDEX {idx_name} ON {tname}({idx_cols});')

        return '\n'.join(lines)

    def _generate_views(self, views: list[ViewInfo]) -> str:
        lines = ['-- Views']
        target = self.target
        for view in views:
            vname = self._quote(view.name)
            definition = view.definition.rstrip(';')
            if target == 'mssql':
                lines.append(f'CREATE OR ALTER VIEW {vname} AS')
            elif target == 'sqlite':
                lines.append(f'CREATE VIEW IF NOT EXISTS {vname} AS')
            else:
                lines.append(f'CREATE OR REPLACE VIEW {vname} AS')
            lines.append(definition + ';')
        return '\n'.join(lines)

    def _generate_triggers(self, triggers: list[TriggerInfo]) -> str:
        lines = ['-- Triggers']
        for trig in triggers:
            tname = self._quote(trig.name)
            body = trig.body.strip()
            target = self.target

            if target == 'postgresql':
                lines.append(f'-- Trigger: {trig.name}')
                if trig.table_name:
                    tname_ref = self._quote(trig.table_name)
                    lines.append(f'CREATE OR REPLACE FUNCTION {self._quote(f"func_{trig.name}")}() RETURNS TRIGGER AS $$')
                    lines.append(body)
                    lines.append(f'$$ LANGUAGE plpgsql;')
                    lines.append(f'CREATE TRIGGER {tname} {trig.event} ON {tname_ref} FOR EACH ROW EXECUTE FUNCTION {self._quote(f"func_{trig.name}")}();')
                else:
                    lines.append(f'-- Evento: {trig.event}')
                    lines.append(f'-- Código original:')
                    for line in body.split('\n'):
                        lines.append(f'-- {line}')
            elif target in ('mysql', 'mariadb'):
                lines.append(f'-- Trigger: {trig.name}')
                if trig.table_name:
                    tname_ref = self._quote(trig.table_name)
                    delim = '//'
                    lines.append(f'DELIMITER {delim}')
                    lines.append(f'CREATE TRIGGER {tname} {trig.event} ON {tname_ref} FOR EACH ROW')
                    lines.append(f'BEGIN')
                    for line in body.split('\n'):
                        lines.append(f'  {line}')
                    lines.append(f'END{delim}')
                    lines.append(f'DELIMITER ;')
                else:
                    lines.append(f'-- Código original (adaptar para MySQL):')
                    for line in body.split('\n'):
                        lines.append(f'-- {line}')
            elif target == 'mssql':
                lines.append(f'-- Trigger: {trig.name}')
                if trig.table_name:
                    tname_ref = self._quote(trig.table_name)
                    lines.append(f'CREATE TRIGGER {tname} ON {tname_ref} {trig.event}')
                    lines.append(f'AS')
                    lines.append(f'BEGIN')
                    for line in body.split('\n'):
                        lines.append(f'  {line}')
                    lines.append(f'END;')
                else:
                    lines.append(f'-- Código original (adaptar para MSSQL):')
                    for line in body.split('\n'):
                        lines.append(f'-- {line}')
            elif target == 'oracle':
                lines.append(f'-- Trigger: {trig.name}')
                if trig.table_name:
                    tname_ref = self._quote(trig.table_name)
                    lines.append(f'CREATE OR REPLACE TRIGGER {tname}')
                    lines.append(f'{trig.event} ON {tname_ref} FOR EACH ROW')
                    lines.append(f'BEGIN')
                    for line in body.split('\n'):
                        lines.append(f'  {line}')
                    lines.append(f'END;')
                else:
                    lines.append(f'-- Código original (adaptar para Oracle):')
                    for line in body.split('\n'):
                        lines.append(f'-- {line}')
            elif target == 'sqlite':
                lines.append(f'-- Trigger: {trig.name}')
                if trig.table_name:
                    tname_ref = self._quote(trig.table_name)
                    lines.append(f'CREATE TRIGGER {tname} {trig.event} ON {tname_ref}')
                    lines.append(f'BEGIN')
                    for line in body.split('\n'):
                        lines.append(f'  {line}')
                    lines.append(f'END;')
                else:
                    lines.append(f'-- Código original (adaptar para SQLite):')
                    for line in body.split('\n'):
                        lines.append(f'-- {line}')
            else:
                lines.append(f'-- Trigger: {trig.name}')
                if trig.table_name:
                    lines.append(f'-- Criar em {target}: associe à tabela {self._quote(trig.table_name)}')
                for line in body.split('\n'):
                    lines.append(f'-- {line}')
        return '\n'.join(lines)

    def _generate_procedures(self, procedures: list[ProcedureInfo]) -> str:
        lines = ['-- Stored Procedures / Functions']
        for proc in procedures:
            lines.append(f'-- PROCEDURE: {proc.name}')
            if proc.source:
                for line in proc.source.split('\n'):
                    lines.append(f'-- {line}')
            lines.append(f'--')
            lines.append(f'-- Adaptar manualmente para {self.target}:')
            lines.append(f'-- CREATE OR REPLACE FUNCTION "{proc.name}"(...)')
            lines.append(f'-- RETURNS ... LANGUAGE plpgsql AS $$')
            lines.append(f'-- BEGIN')
            lines.append(f'--   ...')
            lines.append(f'-- END;')
            lines.append(f'-- $$;')
        return '\n'.join(lines)

    def _quote(self, name: str) -> str:
        if not name:
            return name
        target = self.target
        if target in ('mysql', 'mariadb'):
            return f'`{name}`'
        if target == 'mssql':
            return f'[{name}]'
        return f'"{name}"'
