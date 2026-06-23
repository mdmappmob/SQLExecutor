# SQL Executor

Aplicação desktop para execução de comandos SQL em **Microsoft SQL Server**, **Oracle** e **Firebird**.

**Tecnologias:** Python 3.14, PySide6 6.11 (Qt), pyodbc, oracledb, fdb, sqlglot, Clean Architecture

**Copyright:** Márcio Donizeti Marcondes

---

## Sumário

- [Instalação](#instalação)
- [Conexão](#conexão)
- [Editor SQL](#editor-sql)
- [Parâmetros](#parâmetros)
- [Execução](#execução)
- [Grid de Resultados](#grid-de-resultados)
- [Importar CSV](#importar-csv)
- [Navegador de Schemas](#navegador-de-schemas)
- [Histórico](#histórico)
- [Favoritos](#favoritos)
- [Sessão](#sessão)
- [Oracle](#oracle)
- [Firebird](#firebird)
- [Atalhos de Teclado](#atalhos-de-teclado)
- [Arquivos de Log](#arquivos-de-log)
- [Build](#build)
- [Estrutura do Projeto](#estrutura-do-projeto)

---

## Instalação

### Requisitos

- Python 3.12 ou superior
- Para **SQL Server**: ODBC Driver 17 ou 18 ([Download](https://go.microsoft.com/fwlink/?linkid=2293649))
- Para **Oracle**: as DLLs do Instant Client já são bundled no executável (Oracle 11c+)
- Para **Firebird**: a fbclient.dll já é bundled no executável (Firebird 2.5+)

### Dependências

```bash
pip install PySide6>=6.6.0 pyodbc>=5.0.0 oracledb>=2.0.0 fdb>=2.0.0 sqlglot>=25.0.0 openpyxl>=3.1.0
```

### Executar

```bash
python main.py
```

---

## Conexão

O aplicativo suporta três bancos de dados, selecionáveis no diálogo de conexão:

| Banco | Driver | Autenticação |
|---|---|---|
| **SQL Server** | ODBC (`pyodbc`) | Windows / SQL Server |
| **Oracle** | Oracle Client (`oracledb` thick mode) | Usuário/senha |
| **Firebird** | `fdb` (via fbclient.dll bundled) | Usuário/senha |

### MSSQL
- **Servidor:** `localhost\SQLEXPRESS` ou `192.168.1.100,1433`
- **Database:** nome do banco

### Oracle
- **Servidor:** oculto (não usado)
- **Database:** DSN completo: `host:porta/serviço` (Easy Connect)
  - Ex.: `192.168.1.100:1521/ORCL`
  - TNS names não são suportados (DPY-4027)

### Firebird
- **Servidor:** oculto (não usado)
- **Database:** caminho completo do banco ou host:porta/caminho
  - Ex.: `C:\dados\BANCO.FDB` ou `192.168.1.100:3050/C:\dados\BANCO.FDB`

### Auto-conexão

Ao iniciar, se houver configuração salva, o aplicativo tenta conectar automaticamente. Configurações antigas (com servidor e database separados) são migradas automaticamente.

---

## Editor SQL

### Abas múltiplas

- Botão **+** no canto direito da barra de abas
- Duplo clique na aba para renomear
- Atalhos:
  - `Ctrl+S` — Salvar aba atual
  - `Ctrl+Shift+S` — Salvar como...
  - `Ctrl+O` — Abrir arquivo `.sql`

### Syntax Highlighting

Destaque de sintaxe SQL com temas claro/escuro (VS Code Dark):

| Token | Cor |
|---|---|
| Palavras-chave (SELECT, FROM, WHERE...) | Amarelo claro `#DCDCAA` |
| Strings (`'texto'`) | Laranja `#F0C674` |
| Números | Verde claro `#B5E853` |
| Comentários (`--`, `/* */`) | Cinza `#5C6370` (itálico) |
| Operadores | Laranja `#D19A66` |

### Context Menu

Clique direito no editor para:
- Abrir SQL, Salvar, Salvar como...
- **Formatar SQL** (usa `sqlglot` — formata CTEs, JOINs, CASE, UNION)
- **Salvar como Favorito**
- **Executar (F9)**

### Localizar e Substituir

| Atalho | Função |
|---|---|
| `Ctrl+F` | Localizar |
| `Ctrl+H` | Localizar + Substituir |
| `F3` / `Shift+F3` | Próximo / anterior |

- Realce em tempo real
- Contador de resultados
- Botão **Aa** para case-sensitive

---

## Parâmetros

Suporte a parâmetros nomeados com `:nome`:

```sql
SELECT * FROM usuarios WHERE id = :id
```

- `:param` dentro de aspas → tratado como texto
- `= :param` → tratado como número
- `::` (dois pontos duplos) ignorado (cast SQL Server)
- Datas `dd/mm/yyyy` convertidas para `YYYYMMDD`

---

## Execução

Comandos permitidos: **SELECT**, **INSERT**, **UPDATE**, **DELETE**.

- CTEs (`WITH`) são suportados
- **DELETE/UPDATE sem WHERE**: confirmação antes de executar
- Botão **Executar (F9)** com ícone play branco sobre fundo verde

---

## Grid de Resultados

### Formatação

- Números exibidos sem formatação (valor cru)
- Datas: `dd/mm/aaaa HH:MM:SS`
- `NULL` exibido em itálico cinza
- Colunas numéricas alinhadas à direita

### Abas

- **Resultados**: grid com dados
- **Mensagens**: logs de execução e salvamento

### Paginação

Controles: Primeira, ←, Página X/Y, →, Última. Tamanhos: 50, 100, 200, 500, 1000.

### Edição Inline

Disponível para `SELECT` de tabela única (sem JOIN/UNION/subquery).

- Duplo clique para editar
- Células alteradas ficam com fundo amarelo
- `Ctrl+V` para colar TSV
- **Salvar Alterações**: gera UPDATE/INSERT automaticamente
- Parsing inteligente de números no formato brasileiro (ex.: `2.019` → `2019`)

### Exportar

Botão com menu dropdown:
- **CSV** — UTF-8-BOM
- **Excel** — via `openpyxl` com cabeçalho estilizado

---

## Importar CSV

Assistente completo:
1. Selecionar arquivo
2. Configurar delimitador (auto-detect, vírgula, ponto e vírgula, tab, pipe)
3. Prévia das primeiras 10 linhas
4. Mapeamento de colunas (botão "Buscar Colunas" consulta o banco)
5. Importação em lote (100–10.000)

---

## Navegador de Schemas

Painel acoplável à esquerda que lista tabelas e views do banco conectado.

- Expandir tabela para ver suas colunas (nome, tipo, PK)
- Duplo clique no nome da tabela insere no editor
- Atualizado automaticamente ao conectar/desconectar

---

## Histórico

Painel acoplável à direita que lê `logs/query_log.csv` e exibe as últimas 500 consultas.

- Filtro por texto
- Duplo clique carrega a consulta no editor
- Colunas: timestamp, status, linhas, duração (ms), SQL

---

## Favoritos

Painel de bookmarks para salvar consultas frequentes.

- **Salvar como Favorito** no menu de contexto do editor
- Lista com nome e preview do SQL
- Clique direito: **Carregar** ou **Remover**
- Persistido em `config/bookmarks.json`

---

## Sessão

O aplicativo salva automaticamente as abas abertas ao fechar:

- Conteúdo, nome da aba e caminho do arquivo (se houver)
- Restaurado na próxima inicialização
- Persistido em `config/session.json`

---

## Oracle

### Client Bundled

O executável inclui 7 DLLs do **Oracle Instant Client 19.18 Basic Lite**:

```
infrastructure/oracle_client/
├── oci.dll
├── oraociicus19.dll
├── orannzsbb19.dll
├── oraons.dll
├── ociw32.dll
├── orasql19.dll
└── oraocci19.dll
```

- Modo **thick** ativado automaticamente via `oracledb.init_oracle_client(lib_dir=...)`
- Suporta Oracle **11c** (não suportado pelo thin mode)
- **DPY-4027** (TNS names não encontrado): usar Easy Connect (`host:porta/serviço`)
- **DPY-3010** (servidor 11c não suportado): resolvido com thick mode

---

## Firebird

### Client Bundled

O executável inclui 9 arquivos do **Firebird 2.5.9 Embedded**:

```
infrastructure/firebird_client/
├── fbclient.dll          (fbembed.dll renomeado)
├── icudt30.dll
├── icuin30.dll
├── icuuc30.dll
├── msvcp80.dll
├── msvcr80.dll
├── firebird.msg
├── ib_util.dll
└── Microsoft.VC80.CRT.manifest
```

- `fbclient.dll` adicionado ao `PATH` em runtime antes do `import fdb`
- Suporta **Firebird 2.5+** e **3.0** (conexão remota)
- Funciona sem instalação do Firebird no sistema

---

## Atalhos de Teclado

| Tecla | Ação |
|---|---|
| `F9` / `Ctrl+Return` | Executar SQL |
| `Escape` | Cancelar / fechar busca |
| `Ctrl+F` | Localizar |
| `Ctrl+H` | Localizar + Substituir |
| `F3` / `Shift+F3` | Próximo / anterior resultado |
| `Ctrl+S` | Salvar aba |
| `Ctrl+Shift+S` | Salvar como... |
| `Ctrl+O` | Abrir `.sql` |
| `Ctrl+Shift+C` | Fechar aba |
| `↑` / `↓` (vazio) | Histórico SQL |
| `Tab` / `Shift+Tab` (seleção) | Indentar / outdentar |

---

## Arquivos de Log

Em `logs/`:

| Arquivo | Conteúdo |
|---|---|
| `query_log.csv` | Timestamp, servidor, banco, SQL, sucesso, linhas, duração |
| `error_log.csv` | Timestamp, servidor, banco, SQL, erro |
| `connection_log.csv` | Timestamp, servidor, banco, sucesso |

---

## Build

### Gerar executável

```bash
build.bat
```

Comando PyInstaller:

```bash
pyinstaller --onefile --windowed --name "SQLExecutor" --icon icon.ico ^
  --add-data "domain;domain" --add-data "application;application" ^
  --add-data "infrastructure;infrastructure" --add-data "ui;ui" ^
  --hidden-import pyodbc --hidden-import oracledb --hidden-import fdb ^
  --hidden-import getpass --hidden-import sqlglot --hidden-import openpyxl ^
  --clean --noconfirm main.py
```

Gera `dist\SQLExecutor.exe` (~170 MB devido às DLLs Oracle/Firebird).

### Ícone

O `icon.ico` é gerado via script Python com Pillow: fundo escuro `#2b2b2b` com triângulo play verde `#107c10`.

### Splash Screen

Tela de inicialização com fundo escuro, logotipo play verde, "SQL Executor", versão e copyright.

---

## Estrutura do Projeto

```
SQLExecutor/
├── main.py                         # Ponto de entrada + splash screen + ícone
├── config.ini                      # Configuração salva
├── requirements.txt                # Dependências
├── build.bat                       # Script de build
├── icon.ico                        # Ícone (verde play em fundo escuro)
├── tests.py                        # Testes unitários
│
├── domain/
│   ├── enums.py                    # CommandType, ConnectionStatus
│   ├── value_objects.py            # SQLText, ConnectionConfig (inclui db_type)
│   ├── entities.py                 # SQLCommand, ExecutionResult
│   └── interfaces.py               # DatabaseAdapter + ColumnInfo/TableInfo
│
├── application/
│   └── use_cases.py                # Conexão, execução, validação
│
├── infrastructure/
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── adapter_factory.py      # Factory com lazy imports
│   │   ├── mssql_adapter.py        # pyodbc + get_schema()
│   │   ├── oracle_adapter.py       # oracledb thick + get_schema()
│   │   └── firebird_adapter.py     # fdb + PATH + get_schema()
│   ├── oracle_client/              # 7 DLLs Instant Client 19.18
│   ├── firebird_client/            # 9 arquivos Firebird 2.5 Embedded
│   ├── config_manager.py           # Config.ini (db_type incluso)
│   ├── logger.py                   # Logs CSV
│   ├── csv_parser.py               # Parsing CSV
│   ├── bookmarks.py                # Bookmarks JSON
│   ├── session.py                  # Session save/restore JSON
│   ├── version.py                  # __version__ = "1.0.0"
│   └── i18n.py                     # Internacionalização pt-BR
│
├── ui/
│   ├── main_window.py              # Janela principal, docks, atalhos
│   ├── splash.py                   # Splash screen
│   ├── connection_dialog.py        # Diálogo de conexão (multi-DB)
│   ├── sql_editor.py               # Editor SQL + highlighter + busca
│   ├── result_panel.py             # Grid, edição inline, exportação
│   ├── parameter_dialog.py         # Diálogo :param
│   ├── import_dialog.py            # Importação CSV
│   ├── schema_browser.py           # Navegador de schemas
│   ├── history_panel.py            # Painel de histórico
│   └── bookmarks_panel.py          # Painel de favoritos
│
├── build/                          # PyInstaller build temporário
├── dist/                           # Executável gerado
└── logs/                           # Logs em execução
```

---

## Histórico de Versões

| Versão | Novidades |
|---|---|
| **1.0.0** | Abas múltiplas, parâmetros, formatação, paginação, edição inline, importação CSV, CTEs, logs, atalhos |
| **1.1.0** | Suporte Oracle + Firebird, adapters com get_schema(), schema browser, history panel, bookmarks, session save/restore, Excel export, SQL syntax highlighting, SQL formatter (sqlglot), Oracle Instant Client bundled, Firebird client bundled |

---

## Limitações

- Uma conexão por vez
- Senha salva em texto plano no `config.ini`
- Oracle: apenas Easy Connect (sem TNS)
- Firebird: requer fbclient.dll (bundled ou instalado no sistema)
- Apenas português brasileiro (pt-BR)
