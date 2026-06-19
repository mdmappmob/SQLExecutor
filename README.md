# SQL Executor

Aplicação desktop para execução de comandos SQL em Microsoft SQL Server.

**Tecnologias:** Python 3.12+, PySide6 (Qt), pyodbc, Clean Architecture

---

## Sumário

- [Instalação](#instalação)
- [Como usar](#como-usar)
- [Conexão](#conexão)
- [Editor SQL](#editor-sql)
- [Parâmetros](#parâmetros)
- [Execução](#execução)
- [Grid de Resultados](#grid-de-resultados)
- [Importar CSV](#importar-csv)
- [Atalhos de Teclado](#atalhos-de-teclado)
- [Arquivos de Log](#arquivos-de-log)
- [Build](#build)
- [Estrutura do Projeto](#estrutura-do-projeto)

---

## Instalação

### Requisitos

- Python 3.12 ou superior
- ODBC Driver for SQL Server (versão 17 ou 18 recomendada)
  - [Download Microsoft ODBC Driver](https://go.microsoft.com/fwlink/?linkid=2293649)

### Dependências

```bash
pip install PySide6>=6.6.0 pyodbc>=5.0.0
```

### Executar

```bash
python main.py
```

---

## Como usar

1. Conecte ao SQL Server (preencha servidor, banco e autenticação)
2. Digite ou cole o comando SQL no editor
3. Pressione **F5** ou clique **Executar**
4. Veja os resultados no grid abaixo

Para consultas com parâmetros nomeados (`:param`), um diálogo será exibido automaticamente solicitando os valores.

---

## Conexão

O painel de conexão pode ser recolhido/expandido clicando na seta ao lado do título.

### Campos

| Campo | Descrição |
|---|---|
| **Servidor** | Endereço do SQL Server (ex.: `localhost\SQLEXPRESS` ou `192.168.1.100,1433`) |
| **Banco** | Nome do banco de dados |
| **Autenticação Windows** | Usa o usuário logado no Windows |
| **Autenticação SQL Server** | Requer usuário e senha |
| **Timeout** | Tempo máximo de espera pela conexão (5–120 segundos) |

### Botões

| Botão | Ação |
|---|---|
| **Testar** | Testa a conexão sem salvar |
| **Conectar** | Conecta e salva a configuração |
| **Desconectar** | Encerra a conexão |

### Auto-conexão

Ao iniciar, se houver configuração salva, o aplicativo tenta conectar automaticamente.

---

## Editor SQL

- Editor com fundo escuro e fonte monoespaçada (Consolas 10)
- Comentários `--` e `/* */` são exibidos em itálico
- Comentários são removidos automaticamente antes da execução
- **Histórico**: as últimas 100 consultas ficam disponíveis. Com o editor vazio, use **↑** e **↓** para navegar.
- **Seleção**: se houver texto selecionado, apenas ele é executado

### Localizar e Substituir

| Atalho | Função |
|---|---|
| `Ctrl+F` | Abrir barra de localizar |
| `Ctrl+H` | Abrir localizar + substituir |
| `F3` | Próximo resultado |
| `Shift+F3` | Resultado anterior |
| `Enter` (no campo) | Próximo resultado |
| `Shift+Enter` (no campo) | Resultado anterior |
| `Esc` (no campo) | Fechar barra |

Funcionalidades:
- Realce em tempo real de todas as ocorrências
- Contador de resultados (verde = encontrados, vermelho = nenhum)
- Botão **Aa** para diferenciar maiúsculas/minúsculas
- Substituição individual ou **Subst. Todos**
- Tratamento especial para aspas escapadas SQL (`''`)

### Botões

| Botão | Ação |
|---|---|
| **Importar CSV** | Abre o assistente de importação |
| **Exportar CSV** | Exporta os resultados para CSV |
| **Salvar Alterações** | Persiste edições inline no banco |
| **Executar (F5)** | Executa o comando SQL |

---

## Parâmetros

O SQL Executor suporta parâmetros nomeados no SQL usando `:nome`.

### Sintaxe

```sql
SELECT * FROM usuarios WHERE id = :id
```

```sql
INSERT INTO produtos (nome, preco) VALUES (:nome, :preco)
```

### Comportamento

- Parâmetros são identificados por `:` seguido de letra ou `_` (ex.: `:cod_empresa`)
- `::` (dois pontos duplos) é ignorado (usado para cast no SQL Server)
- Se um parâmetro aparece em uma **linha separada** (ex.: `:cod_empresa` em linha própria), a linha é tratada como declaração visual e removida antes da execução — mas o valor ainda é solicitado e injetado nas ocorrências restantes no SQL
- Parâmetros no **início da mesma linha** do SQL (ex.: `:cod_empresa SELECT ...`) são automaticamente removidos
- Os valores preenchidos são lembrados entre execuções

### Exemplo

```sql
-- Funcionários ativos de uma empresa
:cod_empresa
SELECT nome, salario
FROM funcionarios
WHERE cod_empresa = :cod_empresa
  AND situacao = 'ATIVO'
```

O diálogo solicitará o valor de `cod_empresa` e o SQL executado será:

```sql
SELECT nome, salario
FROM funcionarios
WHERE cod_empresa = 1
  AND situacao = 'ATIVO'
```

---

## Execução

### Validação

Apenas comandos **SELECT**, **INSERT**, **UPDATE** e **DELETE** são permitidos. Comandos DDL (DROP, CREATE, ALTER, TRUNCATE) são bloqueados.

### CTEs (WITH)

CTEs são suportados:

```sql
WITH MaxNivel AS (
    SELECT MAX(nivel) as nivel_max FROM cargos
)
SELECT * FROM cargos WHERE nivel = (SELECT nivel_max FROM MaxNivel)
```

### Segurança

- **DELETE/UPDATE sem WHERE**: exibe confirmação antes de executar
- DELETE sem WHERE também é bloqueado pelo validador interno
- Botões são desabilitados durante a execução

---

## Grid de Resultados

### Abas

- **Resultados**: exibe as linhas retornadas pela consulta
- **Mensagens**: mostra mensagens de execução, erros e resultados de salvamento

### Paginação

Resultados com mais linhas que o tamanho da página são paginados:

| Controle | Função |
|---|---|
| **Primeira** | Primeira página |
| **←** | Página anterior |
| **Página X de Y** | Indicador central |
| **→** | Próxima página |
| **Última** | Última página |
| **Por página:** | 50, 100, 200, 500 ou 1000 linhas |

### Edição Inline

Disponível apenas para `SELECT` de tabela única (sem JOIN, UNION, subquery, CTE).

- Dê duplo clique em uma célula para editar
- Células alteradas ficam com fundo amarelo
- Use **Ctrl+V** para colar dados da área de transferência (TSV)
- Colunas adicionais são criadas automaticamente ao colar além do limite
- Clique **Salvar Alterações** para persistir

O salvamento gera automaticamente:
- **UPDATE** para linhas existentes (usa valores originais como cláusula WHERE)
- **INSERT** para linhas adicionadas
- Type casting automático (date, datetime, int, float) baseado em `INFORMATION_SCHEMA.COLUMNS`

### Exportar CSV

- Botão **Exportar CSV** na barra de ferramentas
- Exporta todas as linhas (não apenas a página atual)
- Codificação UTF-8-BOM
- Nome padrão: `query_result_YYYYMMDD_HHMMSS.csv`

### Exibição de NULL

Valores `NULL` são exibidos em itálico cinza.

---

## Importar CSV

Assistente completo para importação de arquivos CSV:

1. **Selecionar arquivo**: clique **Procurar...** e escolha o CSV
2. **Configurar**: marque se a primeira linha é cabeçalho, escolha o delimitador
3. **Prévia**: visualize as primeiras 10 linhas
4. **Mapeamento**: informe a tabela destino e mapeie as colunas
5. **Buscar Colunas**: consulta `INFORMATION_SCHEMA.COLUMNS` para preencher automaticamente
6. **Importar**: define o tamanho do lote (100–10.000) e executa a importação

### Formatos suportados

| Item | Suporte |
|---|---|
| Delimitadores | Vírgula, ponto e vírgula, tabulação, pipe |
| Codificações | UTF-8-SIG, UTF-16-LE, UTF-16-BE, UTF-8 |
| Extensões | `.csv`, `.txt` |

### Comportamento

- Cada linha é inserida individualmente com `INSERT INTO`
- Em caso de erro em uma linha, as demais continuam sendo processadas
- O primeiro erro é reportado ao final
- Strings `NULL` no CSV são convertidas para `None` (NULL no banco)

---

## Atalhos de Teclado

| Tecla | Ação |
|---|---|
| `F5` | Executar SQL |
| `Ctrl+Return` | Executar SQL |
| `Escape` | Cancelar (fecha busca ou limpa resultados) |
| `Ctrl+F` | Localizar |
| `Ctrl+H` | Localizar + Substituir |
| `F3` | Próximo resultado da busca |
| `Shift+F3` | Resultado anterior da busca |
| `↑` (editor vazio) | Histórico SQL anterior |
| `↓` (editor vazio) | Próximo SQL do histórico |
| `Ctrl+V` (grid editável) | Colar da área de transferência |

---

## Arquivos de Log

O aplicativo mantém três arquivos CSV na pasta `logs/`:

| Arquivo | Conteúdo |
|---|---|
| `query_log.csv` | Timestamp, servidor, banco, SQL, sucesso, linhas afetadas, duração |
| `error_log.csv` | Timestamp, servidor, banco, SQL, erro |
| `connection_log.csv` | Timestamp, servidor, banco, sucesso |

Os logs são criados automaticamente e apenas acrescentados (sem sobrescrita).

---

## Build

Para gerar um executável Windows único:

```bash
build.bat
```

O executável será gerado em `dist\SQLExecutor.exe` (PyInstaller, onefile, windowed).

---

## Estrutura do Projeto

```
SQLExecutor/
├── main.py                     # Ponto de entrada
├── config.ini                  # Configuração de conexão salva
├── requirements.txt            # Dependências
├── build.bat                   # Script de build PyInstaller
├── tests.py                    # Testes unitários
│
├── domain/                     # Camada de domínio
│   ├── enums.py                # CommandType, ConnectionStatus
│   ├── value_objects.py        # SQLText, ConnectionConfig
│   ├── entities.py             # SQLCommand, ExecutionResult
│   └── interfaces.py           # DatabaseAdapter, CommandValidator, AuditLogger
│
├── application/                # Casos de uso
│   └── use_cases.py            # Conexão, execução, validação
│
├── infrastructure/             # Infraestrutura
│   ├── mssql_adapter.py        # Conexão ODBC SQL Server
│   ├── config_manager.py       # Persistência config.ini
│   ├── logger.py               # Logs CSV
│   ├── csv_parser.py           # Parsing de CSV
│   └── i18n.py                 # Internacionalização (pt-BR)
│
├── ui/                         # Interface do usuário
│   ├── main_window.py          # Janela principal e atalhos
│   ├── connection_panel.py     # Painel de conexão (recolhível)
│   ├── sql_editor.py           # Editor SQL com localizar/substituir
│   ├── result_panel.py         # Grid com paginação e edição inline
│   ├── parameter_dialog.py     # Diálogo de parâmetros :param
│   └── import_dialog.py        # Assistente de importação CSV
│
└── logs/                       # Criado em execução
    ├── query_log.csv
    ├── error_log.csv
    └── connection_log.csv
```

---

## Limitações

- Apenas SQL Server (ODBC)
- Uma conexão por vez
- Senha salva em texto plano no `config.ini`
- Histórico SQL apenas em memória (não persiste entre sessões)
- Edição inline requer SELECT de tabela única
- Apenas português brasileiro (pt-BR)
