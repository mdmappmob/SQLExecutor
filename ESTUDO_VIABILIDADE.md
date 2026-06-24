# Estudo de Viabilidade — Sistema Universal + Tradutor SQL

## 1. Análise de Impacto nos Arquivos Existentes

### 1.1 Selecionar banco na interface (ConnectionPanel)

| Arquivo | Impacto |
|---|---|
| `ui/connection_panel.py` | Adicionar um `QComboBox` com os bancos suportados (MSSQL, Oracle, Firebird, MySQL, MariaDB, PostgreSQL). O seletor deve vir antes dos campos de conexão, pois o tipo de banco determina os campos seguintes (ex: Oracle precisa de `service_name` ou `SID`; Firebird usa caminho de arquivo `.fdb`). |
| `ui/main_window.py` | O `_on_connect` precisa passar o tipo de banco selecionado para o use case. |
| `application/use_cases.py` | `ConnectionUseCase.connect()` e `ConnectionUseCase.test_connection()` precisam receber o tipo de banco para instanciar o adapter correto. |
| `infrastructure/config_manager.py` | Gerencia config em `%APPDATA%/SQLExecutor/sqlexecutor.ini` + senha no Credential Manager via `keyring`. Campo `db_type` na seção `[Connection]`. |
| `domain/value_objects.py` | `ConnectionConfig` precisa de um campo `db_type: str`. |
| `domain/interfaces.py` | A interface `DatabaseAdapter` já está genérica — não precisa de alterações. |
| `infrastructure/mssql_adapter.py` | Renomear para `adapters/mssql_adapter.py` (dentro de nova pasta) ou manter como está e criar os novos no mesmo padrão. |

### 1.2 Factory de adapters

| Arquivo | Impacto |
|---|---|
| `infrastructure/` | Nova pasta `infrastructure/adapters/` com um adapter por banco e um `adapter_factory.py` |
| `infrastructure/__init__.py` | Se necessário, expor a factory |
| `application/use_cases.py` | Receber o adapter via injeção, ou usar a factory internamente |

### 1.3 Tradutor SQL

| Arquivo | Impacto |
|---|---|
| `domain/dialect/` (nova) | Módulo com o core do tradutor |
| `domain/dialect/ast.py` | Nodes da AST (Select, Insert, etc.) |
| `domain/dialect/parser.py` | Parser SQL → AST |
| `domain/dialect/dialect_base.py` | Classe base abstrata para dialetos |
| `domain/dialect/dialects/mssql.py` | Regras de output para MSSQL |
| `domain/dialect/dialects/oracle.py` | Regras para Oracle |
| `domain/dialect/dialects/firebird.py` | Regras para Firebird |
| `domain/dialect/dialects/mysql.py` | Regras para MySQL |
| `domain/dialect/dialects/mariadb.py` | Regras para MariaDB |
| `domain/dialect/dialects/postgresql.py` | Regras para PostgreSQL |
| `domain/dialect/translator.py` | Classe orquestradora: parser → AST → dialeto alvo |
| `infrastructure/sql_presets.py` (novo) | Catálogo de comandos SQL pré-formatados por dialeto |

---

## 2. Proposta de Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                        UI Layer                                  │
│  ConnectionPanel (QComboBox p/ banco)                            │
│  SQLEditor                                                       │
│  ResultPanel                                                     │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                    Application Layer                              │
│  ConnectionUseCase  (recebe db_type, usa factory)                 │
│  SQLExecutionUseCase  (recebe db_type, usa adapter + tradutor)   │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                    Domain Layer                                   │
│  interfaces/DatabaseAdapter  (já existe, genérico)               │
│  dialect/parser.py → AST                                         │
│  dialect/dialect_base.py                                         │
│  dialect/dialects/{mssql,oracle,firebird,...}.py                 │
│  dialect/translator.py  (orquestra parser + dialeto)             │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                 Infrastructure Layer                               │
│  adapters/                                                       │
│    ├── __init__.py                                                │
│    ├── adapter_factory.py   ← registry dos adapters              │
│    ├── mssql_adapter.py     ← já existe, mover p/ cá            │
│    ├── oracle_adapter.py                                         │
│    ├── firebird_adapter.py                                       │
│    ├── mysql_adapter.py                                          │
│    ├── mariadb_adapter.py                                        │
│    └── postgresql_adapter.py                                     │
│  config_manager.py         ← adicionar db_type                  │
└─────────────────────────────────────────────────────────────────┘
```

### Fluxo de conexão universal

```
Usuário seleciona "Oracle" no ComboBox
         │
         ▼
ConnectionPanel.get_config() retorna { db_type: "oracle", server, ... }
         │
         ▼
ConnectionUseCase.connect(db_type, server, database, ...)
         │
         ▼
AdapterFactory.create(db_type) → OracleAdapter()
         │
         ▼
OracleAdapter.connect(config)  ← use case chama o adapter genérico
```

### Fluxo do tradutor SQL (opcional integrado)

```
Usuário digita SQL no dialeto de origem
         │
         ▼
SQLEditor.get_sql()
         │
         ▼
SQLExecutionUseCase.execute(sql, source_dialect, target_dialect)
         │
         ▼
Translator.translate(sql, source="mssql", target="oracle")
    ├── Parser.parse(sql) → AST
    ├── DialectOracle.generate(AST) → SQL convertido
    ▼
Adapter.execute(sql_convertido)
```

---

## 3. Diferenças Principais entre Dialetos (Impacto no Tradutor)

### 3.1 Identificadores (nomes de tabela/coluna)

| Banco | Delimitador | Exemplo |
|---|---|---|
| MSSQL | `[col]` | `SELECT [nome] FROM [tabela]` |
| Oracle | `"col"` (default) | `SELECT "nome" FROM "tabela"` |
| Firebird | `"col"` | `SELECT "nome" FROM "tabela"` |
| MySQL | `` `col` `` | `` SELECT `nome` FROM `tabela` `` |
| MariaDB | `` `col` `` | igual MySQL |
| PostgreSQL | `"col"` | `SELECT "nome" FROM "tabela"` |

### 3.2 Limitação de linhas / TOP

| Operação | MSSQL | Oracle | Firebird | MySQL/MariaDB | PostgreSQL |
|---|---|---|---|---|---|
| Primeiras N linhas | `SELECT TOP N` | `SELECT * FROM (...) WHERE ROWNUM <= N` (11g) ou `FETCH FIRST N ROWS ONLY` (12c+) | `SELECT FIRST N` | `LIMIT N` | `LIMIT N` |
| Paginação (offset) | `OFFSET M ROWS FETCH NEXT N ROWS ONLY` | `OFFSET M ROWS FETCH NEXT N ROWS ONLY` (12c+) / ROWNUM aninhado (11g) | `ROWS M+1 TO M+N` (3.0+) / `FIRST N SKIP M` (2.5) | `LIMIT N OFFSET M` | `LIMIT N OFFSET M` |

### 3.3 Funções de data/hora

| Função | MSSQL | Oracle | Firebird | MySQL | PostgreSQL |
|---|---|---|---|---|---|
| Agora | `GETDATE()` | `SYSDATE` | `CURRENT_TIMESTAMP` | `NOW()` | `NOW()` |
| Hoje (só data) | `CAST(GETDATE() AS DATE)` | `TRUNC(SYSDATE)` | `CURRENT_DATE` | `CURDATE()` | `CURRENT_DATE` |
| Diferença dias | `DATEDIFF(day, d1, d2)` | `d2 - d1` | `DATEDIFF(DAY, d1, d2)` | `DATEDIFF(d1, d2)` | `d2::date - d1::date` |
| Extrair ano | `YEAR(d)` | `EXTRACT(YEAR FROM d)` | `EXTRACT(YEAR FROM d)` | `YEAR(d)` | `EXTRACT(YEAR FROM d)` |

### 3.4 Concatenação de strings

| Banco | Operador |
|---|---|
| MSSQL | `+` |
| Oracle | `\|\|` ou `CONCAT()` |
| Firebird | `\|\|` ou `CONCAT()` |
| MySQL | `CONCAT()` |
| MariaDB | `CONCAT()` |
| PostgreSQL | `\|\|` ou `CONCAT()` |

### 3.5 NULL e identidade

| Funcionalidade | MSSQL | Oracle | Firebird | MySQL | PostgreSQL |
|---|---|---|---|---|---|
| Auto-incremento | `IDENTITY(1,1)` | `GENERATED AS IDENTITY` (12c+) ou `SEQUENCE` | `GENERATED AS IDENTITY` (4.0+) ou `SEQUENCE + TRIGGER` | `AUTO_INCREMENT` | `SERIAL` ou `GENERATED AS IDENTITY` |
| NVL/COALESCE | `ISNULL(a, b)` | `NVL(a, b)` | `COALESCE(a, b)` | `IFNULL(a, b)` | `COALESCE(a, b)` |

### 3.6 Comandos DDL e particulares

| Funcionalidade | MSSQL | Oracle | Firebird | MySQL/MariaDB | PostgreSQL |
|---|---|---|---|---|---|
| Criar tabela | `CREATE TABLE [t]` | `CREATE TABLE "t"` | `CREATE TABLE "t"` | `` CREATE TABLE `t` `` | `CREATE TABLE "t"` |
| Sequência | Não tem (IDENTITY) | `CREATE SEQUENCE` | `CREATE SEQUENCE` (4.0+) ou `GENERATOR` (2.5) | Não tem (AUTO_INCREMENT) | `CREATE SEQUENCE` |
| Comitar | `COMMIT` implícito? Não, explicito | `COMMIT` | `COMMIT` | `COMMIT` | `COMMIT` |

---

## 4. Estimativa de Esforço

### Fase 1 — Sistema Universal (adapters + factory)

| Etapa | Descrição | Esforço estimado |
|---|---|---|
| 1.1 | Refatorar `mssql_adapter.py` para `adapters/`, criar `adapter_factory.py` | 4h |
| 1.2 | Adicionar `db_type` no `ConnectionConfig` e `config_manager.py` | 2h |
| 1.3 | Adicionar `QComboBox` no `ConnectionPanel`, conectar com use case | 4h |
| 1.4 | Implementar `OracleAdapter` (com `python-oracledb`) + testes | 8h |
| 1.5 | Implementar `FirebirdAdapter` (com `fdb`) + testes | 8h |
| 1.6 | Implementar `MySQLAdapter` (com `mysql-connector-python`) + testes | 6h |
| 1.7 | Implementar `MariaDBAdapter` (com `mysql-connector-python`) + testes | 4h |
| 1.8 | Implementar `PostgreSQLAdapter` (com `psycopg3`) + testes | 6h |
| 1.9 | Ajustar `ConnectionUseCase` e `SQLExecutionUseCase` para usar factory | 4h |
| 1.10 | Testes de integração completos | 8h |
| **Total Fase 1** | | **~54 horas (7 dias úteis)** |

### Fase 2 — Tradutor SQL (básico)

| Etapa | Descrição | Esforço estimado |
|---|---|---|
| 2.1 | Estudar e selecionar biblioteca de parsing (sqlglot vs manual) | 4h |
| 2.2 | Definir AST nodes básicos (Select, Insert, Delete, Update, Expression) | 6h |
| 2.3 | Implementar parser SQL → AST (com sqlglot ou manual) | 20h |
| 2.4 | Dialeto MSSQL (gerador de SQL a partir da AST) | 8h |
| 2.5 | Dialeto Oracle (gerador) | 8h |
| 2.6 | Dialeto Firebird (gerador) | 8h |
| 2.7 | Dialeto MySQL/MariaDB (gerador) | 6h |
| 2.8 | Dialeto PostgreSQL (gerador) | 6h |
| 2.9 | Tradutor orquestrador + testes de roundtrip | 12h |
| 2.10 | Integração com a UI (seletor de dialeto origem/destino) | 6h |
| **Total Fase 2** | | **~84 horas (11 dias úteis)** |

### Total geral estimado: **~138 horas (18 dias úteis)**

---

## 5. Riscos e Mitigação

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| Bibliotecas de BD incompatíveis com Python 3.14 | Média | Alto | Verificar compatibilidade antes; usar fallbacks (ex: `pymysql` se `mysql-connector` falhar) |
| Firebird 2.5 sem suporte a `GENERATED AS IDENTITY` | Alta | Médio | Implementar via `GENERATOR` + `TRIGGER` para versões antigas |
| Oracle 11g não tem `OFFSET/FETCH FIRST` | Alta | Médio | Usar subquery com `ROWNUM` aninhado para paginação |
| sqlglot não cobre edge cases de dialetos antigos | Média | Alto | Ter fallback para "sem tradução" + alerta ao usuário |
| Complexidade do parser SQL para comandos complexos (CTE, window functions, hints) | Alta | Alto | Implementar incremental: começar com SELECT/INSERT/UPDATE/DELETE simples |
| pyodbc é Windows-only para alguns drivers | Média | Médio | Garantir que adapters Oracle/Firebird/PostgreSQL usem drivers nativos Python (não ODBC) |

---

## 6. Roadmap Sugerido

```
Fase 0 — Prova de conceito (1 semana)
├── Criar OracleAdapter funcional (apenas connect/execute)
├── Criar FirebirdAdapter funcional
└── Testar com consultas reais

Fase 1 — Sistema universal (2 semanas)
├── Factory + refactor dos adapters
├── ConnectionPanel com seletor
├── ConfigManager com db_type
├── Adapters: MySQL, MariaDB, PostgreSQL
└── Testes de integração

Fase 2 — Tradutor SQL básico (2 semanas)
├── Parser SQL → AST (SELECT, INSERT, UPDATE, DELETE simples)
├── Geradores: MSSQL, Oracle, Firebird, MySQL, PostgreSQL
├── Tradutor orquestrador
└── Testes de roundtrip (SQL entra em X, sai em Y, executa em Y)

Fase 3 — Tradutor avançado (2 semanas)
├── CTE, subqueries, window functions, JOINs complexos
├── Hints, OPTION, WITH (MSSQL)
├── Hierarchical queries (CONNECT BY - Oracle)
├── Stored procedures / functions (análise apenas)
└── UI de seleção de dialeto origem/destino

Fase 4 — Polimento e testes (1 semana)
├── Tratamento de erros e fallbacks
├── Mensagens de incompatibilidade entre dialetos
├── Documentação
└── Release
```

---

## 7. Recomendação Final

### Sistema Universal (Fase 1) — **RECOMENDADO**

A arquitetura atual já está preparada para isso: a interface `DatabaseAdapter` é genérica, e os use cases já recebem o adapter por injeção. O esforço é moderado (~54h) e o retorno é imediato: o usuário poderá conectar em qualquer banco. 

**Sugestão:** começar pelos adapters Oracle e Firebird (Fase 0 — POC), que são os bancos com versões antigas que você mencionou, e depois expandir.

### Tradutor SQL (Fase 2+) — **RECOMENDADO COM RESSALVAS**

O tradutor é viável, mas o escopo precisa ser bem delimitado:

- **Para queries simples** (SELECT, INSERT, UPDATE, DELETE sem JOINs complexos ou CTEs): a implementação é direta e recomendada.
- **Para queries complexas** (CTEs recursivas, window functions, hints de otimizador, CONNECT BY): o esforço é desproporcional ao benefício para a maioria dos casos de uso.

**Recomendação prática:** implementar o tradutor em 2 camadas:
1. **Camada básica** (Fase 2): SELECT/INSERT/UPDATE/DELETE com WHERE, JOIN, ORDER BY, LIMIT/OFFSET — atende 80% dos casos
2. **Camada avançada** (Fase 3): sob demanda, conforme necessidade real

### Alternativa recomendada: usar [sqlglot](https://github.com/tobymao/sqlglot)

Em vez de implementar um parser manual:
- **Vantagens:** parsing robusto, 20+ dialetos suportados, AST madura, open source ativo, compatível com Python 3.14
- **Desvantagens:** não cobre 100% dos dialetos antigos (Firebird 2.5, Oracle 11g edge cases); necessário customizar para versões específicas
- **Estratégia:** usar sqlglot como base e estender com regras próprias para Firebird 2.5 e Oracle 11g

```
┌──────────┐    ┌──────────┐    ┌──────────────┐
│ SQL input│───▶│ sqlglot  │───▶│ AST          │
└──────────┘    │ .parse() │    └──────┬───────┘
                └──────────┘           │
                ┌──────────────────────▼───────┐
                │  DialectGenerator (custom)    │
                │  ├── MSSQLGenerator           │
                │  ├── Oracle11gGenerator       │
                │  ├── Firebird25Generator      │
                │  └── ...                      │
                └──────────────────────┬───────┘
                                       ▼
                               ┌──────────────┐
                               │ SQL output   │
                               └──────────────┘
```
