# SQL Executor — Documentação Completa

**Versão:** 1.1.0  
**Build:** 2026.06.23  
**Autor:** Márcio Donizeti Marcondes

---

## Índice

1. [Visão Geral](#1-visão-geral)
2. [Instalação](#2-instalação)
3. [Interface Principal](#3-interface-principal)
4. [Gerenciamento de Conexão](#4-gerenciamento-de-conexão)
5. [Editor SQL](#5-editor-sql)
6. [Painel de Resultados](#6-painel-de-resultados)
7. [Importação CSV](#7-importação-csv)
8. [Navegador de Schema](#8-navegador-de-schema)
9. [Histórico](#9-histórico)
10. [Favoritos (Bookmarks)](#10-favoritos-bookmarks)
11. [Tradutor SQL](#11-tradutor-sql)
12. [Logs de Auditoria](#12-logs-de-auditoria)
13. [Atalhos de Teclado](#13-atalhos-de-teclado)
14. [Arquivos de Configuração](#14-arquivos-de-configuração)
15. [Build e Distribuição](#15-build-e-distribuição)
16. [Arquitetura do Projeto](#16-arquitetura-do-projeto)

---

## 1. Visão Geral

O **SQL Executor** é uma aplicação desktop para execução de comandos SQL em múltiplos bancos de dados relacionais. Suporta **6 dialetos**:

| Banco | Driver | Adapter |
|---|---|---|
| SQL Server (MSSQL) | `pyodbc` | `MSSQLAdapter` |
| Oracle | `oracledb` | `OracleAdapter` |
| Firebird | `fdb` | `FirebirdAdapter` |
| MySQL | `pymysql` | `MySQLAdapter` |
| MariaDB | `pymysql` | `MariaDBAdapter` |
| PostgreSQL | `psycopg2` | `PostgreSQLAdapter` |

### Funcionalidades principais

- Editor SQL com múltiplas abas, syntax highlight, find/replace
- Execução de SELECT, INSERT, UPDATE, DELETE (DDL bloqueado por segurança)
- Paginação de resultados (50 a 1000 linhas por página)
- Edição inline de resultados com geração automática de UPDATE/DELETE
- Importação CSV com batch insert e commit/rollback individual
- Navegador de schema (árvore de tabelas/colunas)
- Histórico de comandos executados
- Favoritos (bookmarks)
- Tradutor SQL entre dialetos (sqlglot)
- Logs de auditoria em CSV
- Reconexão automática via sessão persistente

---

## 2. Instalação

### 2.1 Pré-requisitos

- Python 3.10+
- Pip

### 2.2 Criar e ativar ambiente virtual

```powershell
# Criar
python -m venv .venv

# Ativar (Windows)
.venv\Scripts\Activate.ps1

# Ativar (Linux/Mac)
source .venv/bin/activate
```

### 2.3 Instalar dependências

```powershell
pip install -r requirements.txt
```

**Dependências instaladas:**

| Pacote | Finalidade |
|---|---|
| `PySide6` | Interface gráfica (Qt) |
| `pyodbc` | Driver MSSQL |
| `oracledb` | Driver Oracle |
| `fdb` | Driver Firebird |
| `pymysql` | Driver MySQL/MariaDB |
| `psycopg2-binary` | Driver PostgreSQL |
| `openpyxl` | Exportação para Excel |
| `sqlglot` | Parser SQL e tradutor entre dialetos |

### 2.4 Executar

```powershell
python main.py
```

Para abrir um arquivo `.sql` diretamente:

```powershell
python main.py script.sql
```

---

## 3. Interface Principal

A interface é dividida em:

```
┌──────────────────────────────────────────────────────────┐
│  Menu: Conexão | Arquivo                                 │
├──────────────────────────────────────────────────────────┤
│  [Importar CSV] [Traduzir] [Salvar] [Exportar]  [▶ Executar] │
├───────────┬──────────────────────────────────────────────┤
│ Navegador │  Editor SQL (abas)                           │
│ (esquerda)│                                              │
│           ├──────────────────────────────────────────────┤
│           │  Resultados / Mensagens (abas)               │
│           │                                              │
├───────────┴──────────────────────────────────────────────┤
│ Status: [MSSQL] Servidor\Banco    | v1.1.0               │
└──────────────────────────────────────────────────────────┘
```

### 3.1 Painéis laterais (dock widgets)

- **Navegador** (esquerda): árvore de tabelas/views do banco conectado
- **Histórico** (direita): comandos executados recentemente
- **Favoritos** (direita): queries salvas como favoritas

Todos os painéis podem ser movidos, fechados ou redimensionados.

### 3.2 Barra de status

Exibe:
- Tipo de banco conectado (ex: `[MSSQL]`)
- Servidor e banco
- Botão **X** vermelho para desconectar
- Versão do aplicativo

---

## 4. Gerenciamento de Conexão

### 4.1 Conectar

**Atalho:** `Ctrl+Shift+C`

1. Clique em **Conexão > Conectar** ou pressione `Ctrl+Shift+C`
2. No diálogo, selecione o **tipo de banco**
3. Preencha os campos:
   - **MSSQL:** servidor (ex: `192.168.1.100,1433`), database
   - **Oracle:** database/SID (ex: `localhost:1521/XEPDB1`)
   - **Firebird:** caminho do banco (ex: `localhost/3050:C:\db\banco.fdb`)
   - **MySQL/MariaDB:** servidor, database/schema
   - **PostgreSQL:** servidor, database
4. Informe usuário e senha (ou Windows Auth para MSSQL)
5. Clique em **Testar** para validar a conexão
6. Clique em **Conectar**

### 4.2 Auto-conexão

Se o `config.ini` tiver uma configuração salva, o SQL Executor tenta conectar automaticamente ao iniciar.

### 4.3 Sessão persistente

Ao conectar com sucesso, a sessão é salva em `config/session.json`. Na próxima inicialização, o sistema restaura a conexão automaticamente.

### 4.4 Desconectar

- Clique no botão **X** vermelho na barra de status
- Ou **Conexão > Desconectar**

---

## 5. Editor SQL

### 5.1 Abas múltiplas

- Cada aba é um editor SQL independente
- Botão **+** (ou `Ctrl+T`) abre nova aba
- Botão **✕** fecha a aba atual
- Duplo clique na aba para renomear

### 5.2 Syntax Highlight

Destaca automaticamente:
- Palavras-chave SQL (`SELECT`, `FROM`, `WHERE`, etc.) em azul
- Strings (`'texto'`) em verde
- Números em laranja
- Comentários (`--` e `/* */`) em cinza

### 5.3 Executar SQL

- **F9** ou **Ctrl+Enter**: executa o SQL da aba atual
- Se houver texto selecionado, executa apenas a seleção
- Se não houver seleção, executa o conteúdo completo da aba

### 5.4 Comandos permitidos

Apenas os seguintes comandos podem ser executados:

| Comando | Observação |
|---|---|
| `SELECT` | Qualquer consulta |
| `INSERT` | Apenas VALUES |
| `UPDATE` | Requer WHERE |
| `DELETE` | **Exige WHERE** (bloqueado sem) |
| CTE (`WITH`) | Permitido se o comando final for SELECT/INSERT/UPDATE/DELETE |

**DDL bloqueado:** `CREATE`, `DROP`, `ALTER`, `TRUNCATE`, `GRANT`, `REVOKE` são rejeitados.

### 5.5 Parâmetros nomeados

Use `:nome` no SQL para parâmetros:

```sql
SELECT * FROM funcionarios
WHERE data_admissao >= :data_inicio
  AND salario > :salario_min
```

Ao executar, um diálogo solicita os valores. Os parâmetros são:
- Injetados com aspas se estiverem entre `'` ... `'`
- Injetados como números se precedidos por `=`, espaço, `(`, `,`, `>`, `<`, `!`
- Datas no formato `dd/mm/aaaa` são convertidas automaticamente

### 5.6 Comentários

- `--` comentário de linha
- `/* */` comentário de bloco (multilinha)
- Comentários são ignorados na execução e validação

### 5.7 Find / Replace

| Ação | Atalho |
|---|---|
| Abrir busca | `Ctrl+F` |
| Abrir substituir | `Ctrl+H` |
| Buscar próximo | `F3` |
| Buscar anterior | `Shift+F3` |
| Fechar busca | `Escape` |

### 5.8 Abrir arquivo SQL

- `Ctrl+O`
- Ou arraste o arquivo `.sql` para o ícone do aplicativo

### 5.9 Salvar arquivo SQL

| Ação | Atalho |
|---|---|
| Salvar aba atual | `Ctrl+S` |
| Salvar como... | `Ctrl+Shift+S` |

---

## 6. Painel de Resultados

### 6.1 Abas

- **Resultados:** tabela com dados retornados
- **Mensagens:** log detalhado da execução

### 6.2 Paginação

- Botões: `|◄` `◄` [Página] `►` `►|`
- Tamanho da página ajustável: 50, 100, 200, 500, 1000

### 6.3 Formatação de células

- **NULL**: exibido em itálico cinza
- **Números**: alinhados à direita
- **Moeda/Decimais**: mantém formatação original
- **Datas**: exibidas no formato `dd/mm/aaaa HH:MM:SS`

### 6.4 Edição inline

Para tabelas identificadas automaticamente (SELECT de tabela única):

1. Clique duas vezes em uma célula para editar
2. Células alteradas ficam com fundo **amarelo**
3. Clique em **Salvar alterações** (botão amarelo)
   - Células modificadas geram `UPDATE`
   - Novas linhas (coladas no final) geram `INSERT`
4. Confirme no diálogo

**Restrições:** a edição inline é MSSQL-otimizada (usa `[col]` e `?` placeholders).

### 6.5 Colar dados

`Ctrl+V` em uma célula:
- Dados de planilhas (Excel, Google Sheets) são reconhecidos
- Abas (`\t`) separam colunas, novas linhas separam registros
- Dados colados em novas linhas são tratados como INSERT

### 6.6 Exportar

| Formato | Ação |
|---|---|
| **CSV** | Clique em **Exportar > CSV (.csv)** |
| **Excel** | Clique em **Exportar > Excel (.xlsx)** |

UTF-8 com BOM para CSV. Cabeçalho com formatação para Excel.

### 6.7 Mensagens de erro

Erros de execução são exibidos na aba **Mensagens** com fundo escuro e texto vermelho.

---

## 7. Importação CSV

### 7.1 Abrir

Clique no botão **Importar CSV** na barra de ferramentas do editor.

### 7.2 Passo a passo

1. **Selecionar arquivo:** clique em "Procurar" e escolha o CSV
2. **Configurar:** marque/desmarque "Primeira linha é cabeçalho", escolha delimitador
3. **Visualizar prévia:** tabela com amostra dos dados
4. **Mapear colunas:**
   - Digite o nome da tabela de destino
   - Clique em **Buscar colunas** para auto-preenchimento
   - Ajuste o mapeamento coluna-fonte → coluna-destino
5. **Ajustar batch:** tamanho do lote (100 a 10000 registros)
6. **Importar:** clique em **Importar**

### 7.3 Comportamento

- Cada lote é inserido com `executemany` do adapter
- Cada registro é commitado individualmente
- Se um registro falha, apenas ele é rollbackado (os demais prosseguem)
- Barra de progresso durante a importação
- Relatório final: total inserido (N), erros (M), último erro

---

## 8. Navegador de Schema

Painel lateral esquerdo que exibe a estrutura do banco conectado:

```
📋 NomeDoBanco
├── 📁 Tabelas
│   ├── 📄 funcionarios
│   │   ├── id (INTEGER, PK)
│   │   ├── nome (VARCHAR)
│   │   └── salario (DECIMAL)
│   └── 📄 departamentos
│       └── ...
└── 📁 Views
    └── 📄 vw_relatorio
```

- **Duplo clique** em uma tabela: insere o nome no editor SQL
- O navegador é limpo ao desconectar

---

## 9. Histórico

Painel lateral direito que lista os últimos **500 comandos** executados.

Colunas:
| Data/Hora | Status | Linhas | ms | SQL |
|---|---|---|---|---|
| 23/06 10:30 | ✅ OK | 150 | 45 | SELECT... |
| 23/06 10:29 | ❌ ERRO | 0 | 12 | DELETE... |

- **Filtro:** campo de texto para buscar no SQL
- **Ordenação:** clique nos cabeçalhos das colunas
- **Duplo clique:** carrega o SQL no editor
- **Atualizar:** botão "Atualizar" recarrega do arquivo de log

---

## 10. Favoritos (Bookmarks)

Painel lateral direito para salvar queries frequentes.

### Adicionar favorito

1. Escreva o SQL no editor
2. Clique com botão direito na aba do editor e selecione **Adicionar aos favoritos**  
   *(ou use o menu de contexto no painel de favoritos)*
3. Dê um nome ao favorito

### Gerenciar

- **Duplo clique:** carrega o SQL no editor
- **Clique direito > Remover:** exclui o favorito (com confirmação)
- Salvos em `config/bookmarks.json`

---

## 11. Tradutor SQL

Traduz comandos SQL entre diferentes dialetos de banco.

### 11.1 Como usar

1. Escreva ou abra um SQL no editor
2. Clique no botão **Traduzir** (roxo, na barra de ferramentas)
3. No diálogo:
   - **Dialeto de origem:** preenchido automaticamente com o banco conectado
   - **Dialeto de destino:** selecione o banco de destino
   - O SQL de origem aparece no editor superior (editável)
   - Clique em **Traduzir**
   - O SQL traduzido aparece no editor inferior
4. Clique em **Usar tradução** para inserir o resultado em uma nova aba

### 11.2 Exemplos de tradução

```sql
-- MSSQL (origem)
SELECT TOP 10 nome, salario FROM funcionarios ORDER BY salario DESC

-- Oracle (traduzido)
SELECT nome, salario FROM funcionarios ORDER BY salario DESC NULLS LAST FETCH FIRST 10 ROWS ONLY

-- MySQL
SELECT nome, salario FROM funcionarios ORDER BY salario DESC LIMIT 10

-- Firebird
SELECT FIRST 10 nome, salario FROM funcionarios ORDER BY salario DESC NULLS LAST
```

### 11.3 Funcionalidades suportadas

- `TOP N` → `LIMIT N` / `FETCH FIRST N` / `FIRST N`
- `GETDATE()` → `SYSDATE` / `NOW()` / `CURRENT_TIMESTAMP`
- `ISNULL(a, b)` → `COALESCE(a, b)` / `NVL(a, b)`
- Concatenação: `+` → `||` → `CONCAT()`
- Delimitadores: `[col]` → `"col"` → `` `col` ``
- Paginação: `OFFSET/FETCH` → `LIMIT/OFFSET` → `FIRST/SKIP`
- `DATEADD` → `INTERVAL` / `DATE_ADD`
- `DATEDIFF` → `EXTRACT(epoch...)` / `DATEDIFF`

### 11.4 Limitações

- CTEs recursivas, window functions complexas e hints podem não traduzir completamente
- Oracle 11g `ROWNUM` precisa de ajuste manual em queries muito complexas
- Firebird 2.5 `FIRST N SKIP M` é suportado apenas em SELECT simples

---

## 12. Logs de Auditoria

Todos os logs são salvos em `logs/` como CSV com UTF-8 BOM:

| Arquivo | Conteúdo |
|---|---|
| `logs/query_log.csv` | Data, servidor, banco, SQL, sucesso (true/false), linhas afetadas, duração (ms) |
| `logs/error_log.csv` | Data, servidor, banco, SQL, mensagem de erro |
| `logs/connection_log.csv` | Data, servidor, banco, sucesso (true/false) |

Os logs são acumulativos (append). Use o painel de **Histórico** para consultar.

---

## 13. Atalhos de Teclado

### Editor / Execução

| Atalho | Ação |
|---|---|
| `F9` | Executar SQL |
| `Ctrl+Enter` | Executar SQL |
| `Escape` | Cancelar / Fechar busca |
| `Ctrl+F` | Abrir busca |
| `Ctrl+H` | Abrir substituir |
| `F3` | Buscar próximo |
| `Shift+F3` | Buscar anterior |

### Arquivo

| Atalho | Ação |
|---|---|
| `Ctrl+O` | Abrir arquivo SQL |
| `Ctrl+S` | Salvar aba atual |
| `Ctrl+Shift+S` | Salvar como... |

### Conexão

| Atalho | Ação |
|---|---|
| `Ctrl+Shift+C` | Abrir diálogo de conexão |
| `Alt+F4` | Sair |

---

## 14. Arquivos de Configuração

### `config.ini` (raiz do projeto)

Arquivo INI com a conexão padrão. **Não versionado** (no `.gitignore`).

```ini
[Connection]
db_type = mssql
server = 192.168.1.100,1433
database = ERPMIRA
username = sa
password = Master@321
use_windows_auth = False
timeout = 30
```

### `config/session.json`

Sessão persistente para reconexão automática. **Não versionado**.

### `config/bookmarks.json`

Favoritos do usuário. **Não versionado**.

### `.env`

Variáveis de ambiente (credenciais alternativas). **Não versionado**.

---

## 15. Build e Distribuição

### 15.1 Executável único (Windows)

```powershell
build.bat
```

Gera `dist/SQLExecutor.exe` (modo `--onefile --windowed`).

**Comando PyInstaller equivalente:**

```powershell
python -m PyInstaller --onefile --windowed --name "SQLExecutor" `
    --icon icon.ico `
    --add-data "domain;domain" --add-data "application;application" `
    --add-data "infrastructure;infrastructure" --add-data "ui;ui" `
    --hidden-import pyodbc --hidden-import oracledb --hidden-import fdb `
    --hidden-import pymysql --hidden-import psycopg2 `
    --hidden-import getpass --hidden-import sqlglot `
    --clean --noconfirm main.py
```

### 15.2 Bibliotecas empacotadas

- `infrastructure/oracle_client/`: Oracle Instant Client DLLs (Git LFS)
- `infrastructure/firebird_client/`: fbclient.dll (Git LFS)

São adicionadas automaticamente ao PATH no runtime quando o executável está empacotado.

---

## 16. Arquitetura do Projeto

```
SQLExecutor/
├── main.py                          # Entrypoint + splash screen
├── build.bat                        # Script de build PyInstaller
├── SQLExecutor.spec                 # Spec do PyInstaller
├── requirements.txt                 # Dependências Python
├── config.ini                       # Configuração de conexão (gitignored)
├── .env                             # Variáveis de ambiente (gitignored)
├── icon.ico                         # Ícone do aplicativo
│
├── domain/                          # ——— Camada de Domínio ———
│   ├── entities.py                  # SQLCommand, ExecutionResult, ConnectionSession
│   ├── enums.py                     # CommandType, ConnectionStatus
│   ├── value_objects.py             # ServerName, DatabaseName, SQLText, ConnectionConfig
│   ├── interfaces.py                # DatabaseAdapter, CommandValidator, AuditLogger, ColumnInfo, TableInfo
│   └── dialect/                     # Tradutor SQL
│       ├── __init__.py
│       └── translator.py            # Função translate(sql, source, target)
│
├── application/                     # ——— Camada de Aplicação ———
│   └── use_cases.py                 # ConnectionUseCase, SQLExecutionUseCase, AllowedCommandsValidator
│
├── infrastructure/                  # ——— Camada de Infraestrutura ———
│   ├── version.py                   # __version__, __build__
│   ├── config_manager.py            # Leitura/escrita do config.ini
│   ├── i18n.py                      # Internacionalização (PT-BR)
│   ├── logger.py                    # Auditoria em CSV
│   ├── session.py                   # Sessão persistente (JSON)
│   ├── bookmarks.py                 # Favoritos (JSON)
│   ├── csv_parser.py                # Parser CSV + batch insert
│   ├── oracle_client/               # Oracle Instant Client DLLs (LFS)
│   ├── firebird_client/             # fbclient.dll (LFS)
│   └── adapters/                    # Adaptadores de banco
│       ├── db_types.py              # Enum DBType (mssql, oracle, firebird, mysql, mariadb, postgresql)
│       ├── adapter_factory.py       # Factory com lazy-loading
│       ├── mssql_adapter.py         # MSSQL (pyodbc)
│       ├── oracle_adapter.py        # Oracle (oracledb)
│       ├── firebird_adapter.py      # Firebird (fdb)
│       ├── mysql_adapter.py         # MySQL (pymysql)
│       ├── mariadb_adapter.py       # MariaDB (pymysql, herda MySQLAdapter)
│       └── postgresql_adapter.py    # PostgreSQL (psycopg2)
│
├── ui/                              # ——— Camada de Interface ———
│   ├── main_window.py               # Janela principal, menu, sinais, shortcuts
│   ├── sql_editor.py                # Editor com abas, syntax highlight, find/replace
│   ├── result_panel.py              # Tabela paginada, edição inline, exportação
│   ├── connection_dialog.py         # Diálogo de conexão com seletor de banco
│   ├── import_dialog.py             # Importação CSV com mapeamento
│   ├── parameter_dialog.py          # Diálogo de parâmetros nomeados
│   ├── translate_dialog.py          # Diálogo do tradutor SQL
│   ├── schema_browser.py            # Árvore de tabelas/colunas
│   ├── history_panel.py             # Histórico de comandos
│   └── bookmarks_panel.py           # Gerenciamento de favoritos
│
├── logs/                            # Logs de auditoria (gitignored)
│   ├── query_log.csv
│   ├── error_log.csv
│   └── connection_log.csv
│
└── build/                           # Artefatos de build (gitignored)
    └── SQLExecutor/
```

---

## Fim da documentação
