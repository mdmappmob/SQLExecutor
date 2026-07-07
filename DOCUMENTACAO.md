# SQL Executor — Documentação Completa

**Versão:** 1.3.0  
**Build:** 2026.07.03  
**Autor:** Márcio Donizeti Marcondes

---

## STATUS ATUAL

**Data:** 07/07/2026
**Último commit relevante:** ee49d1b — v1.3.0: SQLite, MariaDB fixes, error messages, migracao universal
**Fase atual:** Liberação de DDL para todos os bancos

### Concluído nesta versão
- [x] SQLite como 7º banco suportado
- [x] MariaDB como dialeto separado
- [x] DDL completo para SQLite (CREATE, ALTER, DROP)
- [x] Migração universal entre bancos (wizard multi-etapa)
- [x] Diálogo Sobre com créditos
- [x] CREATE, ALTER, DROP liberados para todos os bancos

### Em andamento
- [ ] —

---

## Índice

1. [Visão Geral](#1-visão-geral)
2. [Instalação](#2-instalação)
3. [Interface Principal](#3-interface-principal)
4. [Gerenciamento de Conexão](#4-gerenciamento-de-conexão)
5. [Editor SQL](#5-editor-sql)
    - 5.3 [Multi-query (;)](#53-executar-sql)
6. [Painel de Resultados](#6-painel-de-resultados)
    - 6.6 [Geração de scripts (INSERT/UPDATE)](#66-geração-de-scripts-insert--update)
    - 6.8 [Mensagens de erro copiáveis](#68-mensagens-de-erro)
7. [Importação CSV](#7-importação-csv)
8. [Navegador de Schema](#8-navegador-de-schema)
    - 8.1 [Árvore de objetos com FK e índices](#81-árvore-de-objetos)
    - 8.2 [Geração de DDL (CREATE/DROP/SELECT)](#82-ações-disponíveis)
    - 8.3 [PK, FK e índices no CREATE TABLE](#83-ddl-gerado-create-table)
    - 8.4 [Indicador de carregamento](#84-indicador-de-carregamento)
9. [Histórico](#9-histórico)
10. [Favoritos (Bookmarks)](#10-favoritos-bookmarks)
11. [Tradutor SQL](#11-tradutor-sql)
12. [Logs de Auditoria](#12-logs-de-auditoria)
13. [Atalhos de Teclado](#13-atalhos-de-teclado)
14. [Arquivos de Configuração](#14-arquivos-de-configuração)
15. [Build e Distribuição](#15-build-e-distribuição)
16. [Arquitetura do Projeto](#16-arquitetura-do-projeto)
17. [Migração Universal](#17-migração-universal)
18. [Diálogo Sobre](#18-diálogo-sobre)

---

## 1. Visão Geral

O **SQL Executor** é uma aplicação desktop para execução de comandos SQL em múltiplos bancos de dados relacionais. Suporta **7 dialetos**:

| Banco | Driver | Adapter |
|---|---|---|
| SQL Server (MSSQL) | `pyodbc` | `MSSQLAdapter` |
| Oracle | `oracledb` | `OracleAdapter` |
| Firebird | `fdb` | `FirebirdAdapter` |
| MySQL | `pymysql` | `MySQLAdapter` |
| MariaDB | `pymysql` | `MariaDBAdapter` |
| PostgreSQL | `psycopg2` | `PostgreSQLAdapter` |
| **SQLite** | `sqlite3` | `SQLiteAdapter` |

### Funcionalidades principais

- Editor SQL com múltiplas abas, syntax highlight, find/replace
- Execução de SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, DROP
- Paginação de resultados (50 a 1000 linhas por página)
- Edição inline de resultados com geração automática de UPDATE/DELETE
- Importação CSV com batch insert e commit/rollback individual
- Navegador de schema (árvore de tabelas/colunas)
- Histórico de comandos executados
- Favoritos (bookmarks)
- Tradutor SQL entre dialetos (sqlglot)
- Logs de auditoria em CSV
- Reconexão automática via sessão persistente
- Migração universal entre bancos (wizard multi-etapa)
- Diálogo "Sobre" com créditos e versão

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
| `keyring` | Armazenamento seguro de senhas no Credential Manager do SO |
| `sqlite3` | Driver SQLite (built-in, sem instalação adicional) |

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
┌────────────────────────────────────────────────────────────┐
│  Menu: Conexão | Arquivo                                   │
├────────────────────────────────────────────────────────────┤
│  [Importar CSV] [Traduzir] [Salvar] [Exportar]  [▶ Executar] │
├─────────────┬──────────────────────────────────────────────┤
│ Navegador   │  Editor SQL (abas)                           │
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

### 3.2 Barra de ferramentas

| Botão | Ação |
|---|---|
| **Importar CSV** | Abre o diálogo de importação CSV |
| **Traduzir** | Abre o diálogo de tradução SQL |
| **Salvar** | Salva o SQL da aba atual |
| **Exportar** | Exporta resultados para CSV ou Excel |
| **▶ Executar** | Executa o SQL da aba atual |

Os botões possuem altura padronizada com `padding: 8px 16px; font-size: 11px` para consistência visual.

### 3.3 Barra de status

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
   - **SQLite:** caminho do arquivo .db/.sqlite (file picker, sem usuário/senha)
4. Informe usuário e senha (ou Windows Auth para MSSQL)
5. Clique em **Testar** para validar a conexão
6. Clique em **Conectar**

### 4.2 Auto-conexão

Se uma configuração de conexão estiver salva, o SQL Executor tenta conectar automaticamente ao iniciar.

### 4.3 Sessão persistente

Ao conectar com sucesso, a sessão é salva em `config/session.json`. Na próxima inicialização, o sistema restaura a conexão automaticamente.

### 4.4 Desconectar

- Clique no botão **X** vermelho na barra de status
- Ou **Conexão > Desconectar**

### 4.5 Mensagens de erro copiáveis

Todas as mensagens de erro (inclusive do diálogo de conexão) são exibidas em componentes de texto selecionável (`QTextEdit`), permitindo copiar o conteúdo completo com `Ctrl+C` para análise ou suporte.

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
- Se houver **múltiplos comandos separados por `;`**, cada um é executado individualmente e os resultados são exibidos em **abas separadas** ("Resultados 1", "Resultados 2", ...)

### 5.4 Comandos permitidos

Apenas os seguintes comandos podem ser executados:

| Comando | Observação |
|---|---|---|
| `SELECT` | Qualquer consulta |
| `INSERT` | Apenas VALUES |
| `UPDATE` | Requer WHERE |
| `DELETE` | **Exige WHERE** (bloqueado sem) |
| `CREATE` | CREATE TABLE, CREATE INDEX, CREATE VIEW, etc. |
| `ALTER` | ALTER TABLE, ALTER COLUMN, etc. |
| `DROP` | DROP TABLE, DROP INDEX, DROP VIEW, etc. |
| `MIGRACAO` | ✅ Suportado |
| `CTE (WITH)` | Permitido se o comando final for SELECT/INSERT/UPDATE/DELETE |

**Comandos bloqueados:** `TRUNCATE`, `GRANT`, `REVOKE` são rejeitados por segurança.

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

### 6.6 Geração de scripts (INSERT / UPDATE)

Clique com o botão direito na tabela de resultados para gerar scripts diretamente:

- **Copiar como INSERT**: gera comandos `INSERT INTO tabela (colunas) VALUES (valores)` para cada linha selecionada
- **Copiar como UPDATE**: gera comandos `UPDATE tabela SET coluna = valor WHERE ...` para cada linha

Os scripts são inseridos em uma **nova aba no editor SQL**, onde podem ser revisados e executados.

### 6.7 Exportar

| Formato | Ação |
|---|---|
| **CSV** | Clique em **Exportar > CSV (.csv)** |
| **Excel** | Clique em **Exportar > Excel (.xlsx)** |

UTF-8 com BOM para CSV. Cabeçalho com formatação para Excel.

### 6.8 Mensagens de erro

Erros de execução são exibidos na aba **Mensagens** com fundo escuro e texto vermelho. O texto é selecionável, permitindo copiar o erro completo (`Ctrl+C`) para análise.

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

Painel lateral esquerdo que exibe a estrutura do banco conectado.

### 8.1 Árvore de objetos

```
📁 TABLES
├── 📄 funcionarios
│   ├── id (INTEGER, PK)
│   ├── nome (VARCHAR)
│   ├── salario (DECIMAL)
│   ├── 🔗 FK fk_func_depto: departamento_id → departamentos(id)
│   ├── 🔗 FK fk_func_cargo: cargo_id → cargos(id)
│   └── 📊 IDX idx_func_nome (nome)  [UNIQUE]
└── 📄 departamentos
    └── ...
📁 VIEWS
└── 📄 vw_relatorio
📁 PROCEDURES
└── 📄 sp_relatorio_mensal
📁 TRIGGERS
└── 📄 trg_auditoria_update
📁 SEQUENCES (Oracle/PostgreSQL/Firebird)
└── 📄 seq_pedido_id
```

**Legenda:**
- **`PK`** — coluna de chave primária
- **`🔗 FK`** — chave estrangeira (marrom), mostra coluna → tabela(coluna)
- **`📊 IDX`** — índice (verde), mostra colunas e se é UNIQUE

### 8.2 Ações disponíveis

| Ação | Como fazer |
|---|---|---|
| Inserir nome da tabela no editor | **Duplo clique** na tabela |
| Gerar CREATE TABLE | **Clique direito** na tabela → "Gerar CREATE TABLE" |
| Gerar DROP TABLE | **Clique direito** na tabela → "Gerar DROP TABLE" |
| Gerar SELECT * | **Clique direito** na tabela/VIEW → "Gerar SELECT *" |
| Gerar CREATE PROCEDURE/FUNCTION | **Clique direito** na procedure → "Gerar CREATE PROCEDURE" |
| Gerar CREATE TRIGGER | **Clique direito** no trigger → "Gerar CREATE TRIGGER" |

### 8.3 DDL gerado (CREATE TABLE)

O `CREATE TABLE` gerado inclui:
- **Colunas** com tipos e nullable
- **PRIMARY KEY** como `CONSTRAINT PK_NomeTabela PRIMARY KEY (coluna1, ...)`
- **FOREIGN KEY** como `CONSTRAINT FK_NomeTabela_Coluna FOREIGN KEY (col) REFERENCES TabelaRef(col)`
- **Índices** como `CREATE [UNIQUE] INDEX nome_idx ON NomeTabela(col1, col2);`

O `DROP TABLE` gerado inclui `ALTER TABLE ... DROP CONSTRAINT` para cada FK antes do `DROP TABLE IF EXISTS`.

Os scripts são inseridos em uma **nova aba no editor SQL**, prontos para revisão e execução.

### 8.4 Carregamento com overlay e proteção contra travamentos

Ao conectar ou atualizar, um **overlay semi-transparente** cobre a árvore com a mensagem "Carregando schema..." centralizada em destaque. O carregamento pesado é adiado 50ms via `QTimer` para garantir que o overlay renderize antes da consulta, eliminando o congelamento visual.

Se o schema falhar (ex: erro de permissão, consulta inválida), a **mensagem de erro real** é exibida em vermelho na árvore — não apenas um "Erro genérico".

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

## 14. Segurança e Armazenamento de Configuração

### `%APPDATA%/SQLExecutor/sqlexecutor.ini`

A configuração de conexão é salva no diretório de dados do usuário, **fora da pasta do projeto**, para:
- Evitar conflitos com outros sistemas que usam `config.ini`
- Proteger o arquivo contra commits acidentais
- Isolar a configuração por usuário do Windows/Linux

Localização por sistema operacional:

| SO | Caminho |
|---|---|
| Windows | `%APPDATA%\SQLExecutor\sqlexecutor.ini` |
| Linux | `~/.config/SQLExecutor/sqlexecutor.ini` |

**A senha nunca é salva em texto puro.** Ela é armazenada no **gerenciador de credenciais do sistema operacional** através da biblioteca `keyring`:

| SO | Cofre utilizado |
|---|---|
| Windows | Credential Manager (Painel de Controle > Gerenciador de Credenciais) |
| Linux | libsecret (GNOME Keyring / KDE Wallet) |
| macOS | Keychain |

### Fallback (sem keyring)

Se o pacote `keyring` não estiver disponível ou o cofre do SO falhar, a senha é armazenada no próprio INI em **base64** (obfuscação simples — não é criptografia). Neste caso recomenda-se restringir permissões do arquivo ao usuário dono.

### Exemplo do INI (sem senha em texto puro)

```ini
[Connection]
db_type = mssql
server = 192.168.1.100,1433
database = ERPMIRA
username = sa
use_windows_auth = False
timeout = 30
```

### Limpar credenciais salvas

Execute:

```powershell
python -c "from infrastructure.config_manager import ConfigManager; ConfigManager().clear_password()"
```

### `config/session.json`

Sessão persistente para reconexão automática. **Não versionado**. Contém apenas dados de conexão da última sessão (sem senha).

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
    --hidden-import keyring --hidden-import keyring.backends.Windows `
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
├── (config em %APPDATA%/SQLExecutor/sqlexecutor.ini)
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
│   ├── migration/                     # Subsistema de migração
│   │   ├── __init__.py
│   │   ├── type_maps.py               # 27 mapas bidirecionais de tipos
│   │   ├── type_converter.py          # Conversor com detecção de conflitos
│   │   ├── ddl_generator.py           # Gerador de DDL com ordenação topológica
│   │   └── mapping_template.py        # Templates JSON de overrides
│
├── application/                     # ——— Camada de Aplicação ———
│   └── use_cases.py                 # ConnectionUseCase, SQLExecutionUseCase, AllowedCommandsValidator
│
├── infrastructure/                  # ——— Camada de Infraestrutura ———
│   ├── version.py                   # __version__, __build__
│   ├── config_manager.py            # Config em %APPDATA% + senha via keyring
│   ├── i18n.py                      # Internacionalização (PT-BR)
│   ├── logger.py                    # Auditoria em CSV
│   ├── session.py                   # Sessão persistente (JSON)
│   ├── bookmarks.py                 # Favoritos (JSON)
│   ├── csv_parser.py                # Parser CSV + batch insert
│   ├── migration_logger.py         # Logger de migração
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
│       ├── postgresql_adapter.py    # PostgreSQL (psycopg2)
│       └── sqlite_adapter.py         # SQLite (sqlite3)
│
├── ui/                              # ——— Camada de Interface ———
│   ├── main_window.py               # Janela principal, menu, sinais, shortcuts
│   ├── sql_editor.py                # Editor com abas, syntax highlight, find/replace, split_sql_statements()
│   ├── result_panel.py              # Tabela paginada, edição inline, exportação, scripts INSERT/UPDATE
│   ├── connection_dialog.py         # Diálogo de conexão com seletor de banco
│   ├── dialogs.py                   # show_critical() — erro copiável
│   ├── import_dialog.py             # Importação CSV com mapeamento
│   ├── parameter_dialog.py          # Diálogo de parâmetros nomeados
│   ├── translate_dialog.py          # Diálogo do tradutor SQL
│   ├── schema_browser.py            # Árvore de tabelas/colunas com FK, índices, geração de DDL
│   ├── migration_dialog.py         # Wizard de migração (945 linhas)
│   ├── about_dialog.py             # Diálogo Sobre
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

## 17. Migração Universal

Permite migrar o esquema completo de um banco de dados entre diferentes dialetos.

### 17.1 Como acessar

Clique no botão **Migrar** (vermelho) na barra de ferramentas do editor.

### 17.2 Wizard multi-etapa

1. **Origem:** selecione o banco de origem e conecte
2. **Destino:** selecione o banco de destino
3. **Mapeamento:** revise a conversão automática de tipos
   - Tabela interativa com coluna origem → tipo destino
   - Alertas visuais (⚠️) para conversões com possíveis perdas
   - Checkboxes para overrides manuais por coluna
4. **DDL Gerado:** script completo pronto para revisão e execução

### 17.3 Funcionalidades

- **27 mapas bidirecionais** de conversão de tipos entre todos os pares de dialetos
- **Ordenação topológica** de tabelas (respeita dependências FK)
- **Templates JSON** salvos/carregados com overrides por coluna, tabela ou globais
- **Quoting adaptado** por dialeto (`"` para PG, `` ` `` para MySQL, `[]` para MSSQL)
- **Suporte a SQLite** como origem ou destino
- **DDL completo no SQLite**: CREATE TABLE, ALTER TABLE, DROP TABLE, CREATE INDEX, DROP INDEX
- Logs dedicados em `logs/migration_log.csv`

### 17.4 Objetos migrados

| Objeto | Migrado | Observação |
|--------|---------|------------|
| Tabelas (CREATE TABLE) | ✅ | Com PK, FK, constraints, defaults |
| Colunas + tipos | ✅ | Conversão automática com mapa de tipos |
| Sequences | ✅ | PostgreSQL, Oracle, Firebird |
| Views | ✅ | CREATE VIEW |
| Triggers | ✅ | CREATE TRIGGER |
| Procedures/Functions | ✅ | CREATE PROCEDURE/FUNCTION |
| Índices | ✅ | CREATE INDEX |
| **SQLite** | ✅ | Suporta todos os objetos acima |

### 17.5 Exemplo de migração para SQLite

```sql
-- Origem: MySQL
CREATE TABLE usuarios (
  id INT AUTO_INCREMENT PRIMARY KEY,
  nome VARCHAR(50) NOT NULL
);

-- Destino: SQLite (gerado automaticamente)
CREATE TABLE usuarios (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nome TEXT NOT NULL
);
```

### 17.6 Limitações

- Triggers e procedures podem exigir ajuste manual de sintaxe (dialetos muito diferentes)
- Dados (INSERT) não são migrados — apenas estrutura (DDL)
- Firebird 2.5 tem suporte limitado a alguns tipos modernos
- SQLite não suporta sequences (convertido para AUTOINCREMENT quando aplicável)

---

## 18. Diálogo Sobre

Acessível pelo menu **Ajuda > Sobre**.

Exibe:
- Nome e versão do aplicativo
- Build e autor
- Tecnologias utilizadas (Python, PySide6, PyInstaller)
- Bancos suportados (todos os 7)
- Descrição da ferramenta

---

## Fim da documentação
