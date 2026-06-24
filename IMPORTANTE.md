# ⚠ LEITURA OBRIGATÓRIA — SQLExecutor

## 1. Git LFS — ESSENCIAL

DLLs do Oracle e Firebird são rastreadas por **Git LFS** (`.gitattributes`):
```
infrastructure/oracle_client/*.dll
infrastructure/firebird_client/*.dll
infrastructure/firebird_client/*.manifest
infrastructure/firebird_client/firebird.msg
```

Após **qualquer `git clone` ou `git pull`**, execute **OBRIGATORIAMENTE**:

```bash
git lfs pull
```

Sem isso, os arquivos serão **ponteiros LFS de 130 bytes**, e o PyInstaller empacotará um executável sem as DLLs — gerando erro `Failed to load dynlib/dll` em tempo de execução.

---

## 2. Build

```bash
build.bat
```

Equivalente manual:
```bash
pyinstaller --onefile --windowed --name "SQLExecutor" --icon icon.ico ^
  --add-data "domain;domain" --add-data "application;application" ^
  --add-data "infrastructure;infrastructure" --add-data "ui;ui" ^
  --hidden-import pyodbc --hidden-import oracledb --hidden-import fdb ^
  --hidden-import pymysql --hidden-import psycopg2 ^
  --hidden-import getpass --hidden-import sqlglot ^
  --clean --noconfirm main.py
```

Resultado: `dist\SQLExecutor.exe` (~115 MB com DLLs).

Se o executável já existir e estiver rodando, mate o processo antes de rebuildar:
```bash
taskkill /f /im SQLExecutor.exe
```

---

## 3. Estrutura de Diretórios

```
SQLExecutor/
├── main.py                     # Entrypoint + splash + icon generator
├── (config em %APPDATA%/SQLExecutor/sqlexecutor.ini)
├── domain/                     # Clean Architecture: entidades, value objects, interfaces
├── application/                # Use cases
├── infrastructure/
│   ├── adapters/               # 6 adapters + factory + db_types
│   ├── oracle_client/          # DLLs Instant Client 19.18 (Git LFS)
│   └── firebird_client/        # DLLs Firebird 2.5 Embedded (Git LFS)
├── ui/                         # PySide6 widgets
├── dist/                       # Executável gerado (gitignored)
├── build/                      # PyInstaller temporário (gitignored)
├── logs/                       # Logs de auditoria CSV (gitignored)
└── config/                     # session.json, bookmarks.json (gitignored)
```

---

## 4. Skills do opencode Utilizadas

Este projeto utiliza as seguintes skills do opencode para assistência:

| Skill | Uso |
|---|
| `python-fastapi` | Desenvolvimento backend com Python |
| `firebird-sql` | Consultas, procedures e otimização Firebird |
| `mssql` | Consultas, procedures e tuning SQL Server |
| `oracle-sql` | Consultas e tuning Oracle |
| `delphi-expert-master` | Origem do sistema legado (Delphi 7/12), algumas migrações |
| `arquiteto-software` | Modelagem DDD, Clean Architecture |
| `revisor-tecnico` | Revisão de arquitetura, segurança e desempenho |
| `fullstack-brasil` | Orquestrador principal para projetos corporativos BR |
| `ui-brasil` | Padrões visuais brasileiros |
| `contabilidade-br` | Sistemas contábeis e plano de contas BR |
| `auditor` | Verificador de alucinações e suposições |

---

## 5. Documentação Complementar

| Arquivo | Conteúdo |
|---|---|
| `README.md` | Manual do usuário completo |
| `DOCUMENTACAO.md` | Documentação técnica detalhada |
| `CHANGELOG.md` | Histórico de versões |

---

## 6. Armadilhas Conhecidas

- **`QMessageBox.critical`** não permite copiar texto. Toda caixa de erro crítica deve usar `show_critical()` de `ui/dialogs.py`.
- **Botões sem padding/font-size padronizado** ficam com alturas diferentes. Manter `padding: 8px 16px; font-size: 11px` em todos.
- **Firebird/Oracle requerem DLLs reais** — sempre rodar `git lfs pull` antes do build.
- **Config salvo em `%APPDATA%/SQLExecutor/sqlexecutor.ini`** (fora do projeto). Senha vai para o **Credential Manager** via `keyring`. Não há mais senha em texto plano no disco.
- **Não há testes automatizados** — validar manualmente após alterações.
