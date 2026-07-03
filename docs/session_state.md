# Sessão: Migrador Firebird → PostgreSQL — 02/07/2026

## Problema Atual

Execução via `dist\SQLExecutor.exe` (build antigo) — as correções no código-fonte abaixo **não foram testadas**. É preciso rebuildar ou rodar via Python.

### Log do erro

```
Fase 0: Preparando database destino...
  ℹ Database 'pesquisa' já existe
⚠ Erro ao conectar na origem: SQLCODE: -999 / unknown ISC error 335545106
Fase 1: Executando DDL...
  ❌ CREATE INDEX "IDX_DESC" ... → relation "PERGUNTAS" does not exist
  ❌ CREATE INDEX "FK_PESQUISAS_1" ... → relation "PESQUISAS" does not exist
  ❌ CREATE INDEX "FK_PESQUISAS_2" ... → relation "PESQUISAS" does not exist
  ❌ CREATE INDEX "PESQUISAS_IDX1" ... → relation "PESQUISAS" does not exist
  ❌ CREATE INDEX "FK_RESPOSTAS_1" ... → relation "RESPOSTAS" does not exist
  ❌ CREATE INDEX "FK_RESPOSTAS_2" ... → relation "RESPOSTAS" does not exist
  ❌ CREATE UNIQUE INDEX "UNIDADE_IDX1" ... → relation "UNIDADE" does not exist
Fase 2: Copiando dados... ⚠ Origem não conectada
DDL: 0 OK, 7 falha(s) | Dados: 0 linha(s)
```

## Correções Aplicadas no Código-Fonte (NÃO TESTADAS)

### 1. Parsing de statements — `ui/migration_dialog.py:599`
- `ExecutionPage.initializePage()` usava `script.split(";")` + `startswith("--")`
- Comentário `-- Tabela: X` antes de `CREATE TABLE` filtrava o bloco inteiro
- **Fix**: `re.sub(r'^--.*$', '', script, flags=re.MULTILINE)` remove comentários antes de split

### 2. Credenciais da origem — `ui/main_window.py:578`
- `_on_migrate()` passava `username=""`, `password=""`, `port=None`
- Firebird precisa de usuário/senha para conectar (SQLCODE -999)
- **Fix**: carregar do `ConfigManager.load()` em vez de session

### 3. Autocommit CREATE DATABASE — `infrastructure/adapters/postgresql_adapter.py`
- PostgreSQL não permite CREATE DATABASE dentro de transação
- **Fix**: método `execute_autocommit()` que seta `autocommit=True` temporariamente

## Pendências / Próximos Passos (03/07)

1. **Rebuildar o .exe** (`pyinstaller ...`) ou rodar via `.venv\Scripts\python.exe src/main.py`
2. **Testar correção #2** — verificar se `ConfigManager` realmente retorna user/password do Firebird
   - Se `use_windows_auth=True` no config salvo, password não é salva → `_to_conn_cfg()` hardcoded `use_windows_auth=False` → senha vazia
3. **Testar correção #1** — verificar se CREATE TABLE aparece nos statements e executa antes dos índices
4. **Testar correção #3** — CREATE DATABASE já funcionou no último log (`pesquisa já existe`)
5. Verificar ordem das FKs no DDL — tabelas referenciadas devem ser criadas antes

## Arquivos Relevantes Alterados
- `ui/main_window.py` — `_on_migrate()` (linha ~578)
- `ui/migration_dialog.py` — `ScriptPreviewPage.initializePage()` (linha ~599)
- `domain/interfaces.py` — `execute_autocommit()` adicionado
- `infrastructure/adapters/postgresql_adapter.py` — implementação de `execute_autocommit()`
