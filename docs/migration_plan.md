# Plano de Migração entre Bancos de Dados

## 1. Arquitetura Geral

```
┌─────────────────────────────────────────────────────────┐
│                   MigrationWizard (UI)                   │
├─────────────────────────────────────────────────────────┤
│   Step 1    Step 2    Step 3    Step 4    Step 5    Step 6 │
│  Origem →  Destino → Selecionar → Mapear → Preview → Executar │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│              MigrationUseCase (application)              │
├─────────────────────────────────────────────────────────┤
│   extract_schema(source) → convert_types() → generate() │
└─────────────────────────────────────────────────────────┘
                           │
               ┌───────────┴───────────┐
               ▼                       ▼
┌─────────────────────┐   ┌─────────────────────────┐
│   SchemaExtractor   │   │   TypeConverter           │
│   (por adapter)     │   │   (tabelas de mapping)    │
└─────────────────────┘   └─────────────────────────┘
```

---

## 2. Extensões Necessárias no Domínio

### 2.1 ColumnInfo — versão estendida

```python
@dataclass
class ColumnInfo:
    name: str
    data_type: str
    nullable: bool = True
    is_pk: bool = False

    # Novos campos para migração
    default_value: str | None = None
    is_identity: bool = False         # AUTO_INCREMENT / SERIAL / IDENTITY
    identity_start: int | None = None
    identity_increment: int | None = None
    char_length: int | None = None     # VARCHAR(100) → 100
    precision: int | None = None       # DECIMAL(10,2) → 10
    scale: int | None = None           # DECIMAL(10,2) → 2
    character_set: str | None = None
    collation: str | None = None
    check_constraint: str | None = None
    comment: str | None = None
```

### 2.2 Novas entidades

```python
@dataclass
class SequenceInfo:
    name: str
    start_value: int = 1
    increment: int = 1
    min_value: int | None = None
    max_value: int | None = None

@dataclass
class TriggerInfo:
    name: str
    event: str           # BEFORE INSERT, AFTER UPDATE, etc.
    body: str

@dataclass
class ViewInfo:
    name: str
    definition: str       # SQL do CREATE VIEW

@dataclass
class FullSchema:
    tables: list[TableInfo]
    views: list[ViewInfo]
    sequences: list[SequenceInfo]
    triggers: list[TriggerInfo]

@dataclass
class TypeMapping:
    source_type: str
    target_type: str
    conversion_expr: str | None = None   # expressão CAST se necessário
    warning: str | None = None           # aviso para o usuário
```

---

## 3. Tabelas de Mapeamento de Tipos

### 3.1 Firebird → PostgreSQL (exemplo completo)

| Firebird | PostgreSQL | Conversão | Aviso |
|---|---|---|---|
| `SMALLINT` | `SMALLINT` | direto | |
| `INTEGER` | `INTEGER` | direto | |
| `BIGINT` | `BIGINT` | direto | |
| `FLOAT` | `REAL` | direto | |
| `DOUBLE PRECISION` | `DOUBLE PRECISION` | direto | |
| `DECIMAL(p,s)` | `DECIMAL(p,s)` | direto | |
| `NUMERIC(p,s)` | `NUMERIC(p,s)` | direto | |
| `VARCHAR(n)` | `VARCHAR(n)` | direto | |
| `CHAR(n)` | `CHAR(n)` | direto | |
| `BLOB SUB_TYPE TEXT` | `TEXT` | direto | |
| `BLOB SUB_TYPE 0` | `BYTEA` | direto | ⚠ Binário |
| `DATE` | `DATE` | direto | |
| `TIME` | `TIME` | direto | |
| `TIMESTAMP` | `TIMESTAMP` | direto | |
| `BOOLEAN` | `BOOLEAN` | direto | |
| `GENERATOR` (sequence) | `SEQUENCE` | `CREATE SEQUENCE` | |
| Trigger auto-inc | `SERIAL` / `IDENTITY` | converter trigger+generator em `GENERATED AS IDENTITY` | ⚠ Requer validação |
| `VARCHAR(n) CHARACTER SET UTF8` | `VARCHAR(n)` | manter tamanho | ✅ |

### 3.2 Oracle → MariaDB (exemplo parcial)

| Oracle | MariaDB | Conversão | Aviso |
|---|---|---|---|
| `VARCHAR2(n)` | `VARCHAR(n)` | direto | |
| `NVARCHAR2(n)` | `VARCHAR(n) CHARACTER SET utf8mb3` | direto | |
| `CLOB` | `LONGTEXT` | direto | |
| `NCLOB` | `TEXT CHARACTER SET utf8mb3` | direto | |
| `BLOB` | `LONGBLOB` | direto | |
| `RAW(n)` | `VARBINARY(n)` | direto | |
| `NUMBER(p,s)` | `DECIMAL(p,s)` | se s>0 | |
| `NUMBER` (sem params) | `BIGINT` ou `DECIMAL(38)` | ⚠ decisão do usuário |
| `NUMBER(10)` | `INT(10)` | direto | |
| `FLOAT(n)` | `DOUBLE` | direto | |
| `DATE` (com hora) | `DATETIME` | direto | ⚠ Oracle DATE contém hora |
| `TIMESTAMP` | `TIMESTAMP` | direto | |
| `SEQUENCE` | `SEQUENCE` | `CREATE SEQUENCE` (MariaDB 10.3+) | |
| `SYS_GUID()` | `UUID()` | função diferente | |
| `ROWNUM` | `LIMIT` | reescrever query | ❌ Requer análise |
| `SYNONYM` | — | sem equivalente | ❌ Ignorado |

### 3.3 MSSQL → PostgreSQL (exemplo parcial)

| MSSQL | PostgreSQL | Conversão | Aviso |
|---|---|---|---|
| `NVARCHAR(n)` | `VARCHAR(n)` | direto | |
| `NTEXT` | `TEXT` | direto | |
| `IMAGE` | `BYTEA` | direto | |
| `UNIQUEIDENTIFIER` | `UUID` | direto | |
| `MONEY` | `NUMERIC(19,4)` | direto | |
| `SMALLMONEY` | `NUMERIC(10,4)` | direto | |
| `DATETIME2` | `TIMESTAMP` | direto | |
| `DATETIMEOFFSET` | `TIMESTAMPTZ` | direto | |
| `ROWVERSION` | `BYTEA` | direto | ⚠ Semântica diferente |
| `IDENTITY(1,1)` | `GENERATED AS IDENTITY` | direto | |
| `SEQUENCE` | `SEQUENCE` | direto | |
| `SCHEMA` | `SCHEMA` | direto | |
| `GETDATE()` | `NOW()` | função diferente | ✅ sqlglot converte |

---

## 4. Interface do Usuário — Wizard em 6 Etapas

### Tela 1 — Conexão de Origem

```
┌─────────────────────────────────────────────────────────┐
│  Migrar Banco de Dados                            [X]  │
├─────────────────────────────────────────────────────────┤
│  ● Origem    ○ Destino    ○ Seleção    ○ Mapeamento...  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Tipo de Origem:  [Firebird          ▼]                 │
│                                                         │
│  Servidor:  [localhost/3050________________]            │
│  Database:  [C:\dados\banco.fdb___________]             │
│  Usuário:   [SYSDBA________________________________]    │
│  Senha:     [********************************]          │
│                                                         │
│                                    [ Testar Conexão ]   │
│                                                         │
│  Status: ● Conectado                                    │
│                                                         │
│                          [ Voltar ]  [ Próximo > ]      │
└─────────────────────────────────────────────────────────┘
```

### Tela 2 — Conexão de Destino

```
┌─────────────────────────────────────────────────────────┐
│  Migrar Banco de Dados                            [X]  │
├─────────────────────────────────────────────────────────┤
│  ○ Origem    ● Destino    ○ Seleção    ○ Mapeamento...  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Tipo de Destino:  [PostgreSQL           ▼]             │
│                                                         │
│  Servidor:  [vcmm ou 192.168.1.100________________]     │
│  Porta:     [5432                                       │
│  Database:  [meubanco_novo_________________________]    │
│  Usuário:   [postgres______________________________]    │
│  Senha:     [********************************]          │
│                                                         │
│  ☐ Criar database se não existir                        │
│                                                         │
│                                    [ Testar Conexão ]   │
│                                                         │
│  Status: ● Conectado                                    │
│                                                         │
│                          [ Voltar ]  [ Próximo > ]      │
└─────────────────────────────────────────────────────────┘
```

### Tela 3 — Seleção de Objetos

```
┌─────────────────────────────────────────────────────────┐
│  Migrar Banco de Dados                            [X]  │
├─────────────────────────────────────────────────────────┤
│  ○ Origem    ○ Destino    ● Seleção    ○ Mapeamento...  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ☑ Selecionar Todos            [ Filtrar: __________ ] │
│                                                         │
│  ─── Tabelas ───                                       │
│  ☑ CLIENTES                  (15 colunas, 2 FKs)       │
│  ☑ PRODUTOS                  (8 colunas, 1 FK)         │
│  ☑ PEDIDOS                   (12 colunas, 3 FKs)       │
│  ☐ LOG_EXPORTACAO            (5 colunas)   ← pular    │
│                                                         │
│  ─── Views ───                                         │
│  ☑ V_CLIENTES_ATIVOS                                    │
│  ☐ V_RELATORIO_MENSAL                                   │
│                                                         │
│  ─── Sequences ───                                      │
│  ☑ GEN_CLIENTES_ID                                      │
│  ☑ GEN_PRODUTOS_ID                                      │
│  ☑ GEN_PEDIDOS_ID                                       │
│                                                         │
│  Resumo: 5 tabelas, 1 view, 3 sequences selecionadas   │
│                                                         │
│                          [ Voltar ]  [ Próximo > ]      │
└─────────────────────────────────────────────────────────┘
```

### Tela 4 — Revisão de Mapeamento (a mais importante)

```
┌─────────────────────────────────────────────────────────┐
│  Migrar Banco de Dados                            [X]  │
├─────────────────────────────────────────────────────────┤
│  ○ Origem    ○ Destino    ○ Seleção    ● Mapeamento...  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Tabela:  CLIENTES                                      │
│  ┌──────────────────────┬────────────┬────────────┬────┐│
│  │ Coluna               │ Origem     │ Destino    │    ││
│  ├──────────────────────┼────────────┼────────────┼────┤│
│  │ ID_CLIENTE           │ INTEGER    │ INTEGER    │ 🔑 ││
│  │                      │ PK, IDENTITY            │    ││
│  │                      │            ┌──────────┐ │    ││
│  │ NOME                 │ VARCHAR(100) │ VARCHAR(100) │ ││
│  │                      │            └──────────┘ │    ││
│  │ CPF_CNPJ             │ VARCHAR(18) │ VARCHAR(18)  │ ││
│  │ DATA_CADASTRO        │ DATE      │ DATE       │    ││
│  │ SALDO                │ DECIMAL(15,2)│ DECIMAL(15,2)│ ││
│  │ OBSERVACAO           │ BLOB TEXT │ TEXT  ⚠    │    ││
│  │ FOTO                 │ BLOB      │ BYTEA ⚠    │    ││
│  └──────────────────────┴────────────┴────────────┴────┘│
│                                                         │
│  ⚠ Itens que requerem atenção:                          │
│  ┌──────────────────────────────────────────────────────┤│
│  │ ⚠ CLIENTES.ID_CLIENTE: IDENTITY → GENERATED AS...   ││
│  │   [OK, converter]  [Ignorar]  [Editar...]           ││
│  │                                                     ││
│  │ ❌ CLIENTES.FOTO: BLOB binário será BYTEA           ││
│  │   Verifique se o dado binário é necessário          ││
│  └──────────────────────────────────────────────────────┤│
│                                                         │
│                          [ Voltar ]  [ Próximo > ]      │
└─────────────────────────────────────────────────────────┘
```

### Tela 5 — Preview do Script

```
┌─────────────────────────────────────────────────────────┐
│  Migrar Banco de Dados                            [X]  │
├─────────────────────────────────────────────────────────┤
│  ○ Origem    ○ Destino    ○ Seleção    ○ Mapeamento...  │
│  ● Preview   ○ Executar                                  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────────────────────────────────────────────┐│
│  │ -- ==============================================  ││
│  │ -- Script de Migração: Firebird → PostgreSQL       ││
│  │ -- Gerado em: 02/07/2026 15:30                     ││
│  │ -- ==============================================  ││
│  │                                                     ││
│  │ -- Sequences                                       ││
│  │ CREATE SEQUENCE IF NOT EXISTS clientes_id_seq       ││
│  │   START WITH 1 INCREMENT BY 1;                      ││
│  │                                                     ││
│  │ -- Tabela: CLIENTES                                 ││
│  │ CREATE TABLE clientes (                             ││
│  │   id_cliente INTEGER PRIMARY KEY                    ││
│  │     GENERATED BY DEFAULT AS IDENTITY,               ││
│  │   nome VARCHAR(100) NOT NULL,                       ││
│  │   cpf_cnpj VARCHAR(18),                             ││
│  │   data_cadastro DATE DEFAULT CURRENT_DATE,           ││
│  │   saldo DECIMAL(15,2) DEFAULT 0,                    ││
│  │   observacao TEXT,                                   ││
│  │   foto BYTEA                                         ││
│  │ );                                                   ││
│  │                                                     ││
│  │ -- Índices                                         ││
│  │ CREATE INDEX idx_clientes_nome ON clientes(nome);   ││
│  └─────────────────────────────────────────────────────┘│
│                                                         │
│  [ 📋 Copiar ]  [ 💾 Salvar .sql ]                     │
│                                                         │
│                          [ Voltar ]  [ Próximo > ]      │
└─────────────────────────────────────────────────────────┘
```

### Tela 6 — Execução

```
┌─────────────────────────────────────────────────────────┐
│  Migrar Banco de Dados                            [X]  │
├─────────────────────────────────────────────────────────┤
│  ○ Origem    ○ Destino    ○ Seleção    ○ Mapeamento...  │
│  ○ Preview   ● Executar                                  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  [▶ Executar Migração]                                  │
│                                                         │
│  Progresso: ████████████░░░░░░  65%                     │
│  Tabela: CLIENTES — 1.234 linhas inseridas              │
│                                                         │
│  ┌─────────────────────────────────────────────────────┐│
│  │ ✅ CLIENTES          — criada + 1234 linhas        ││
│  │ ✅ PRODUTOS          — criada + 567 linhas         ││
│  │ ✅ PEDIDOS           — criada + 890 linhas         ││
│  │ ⚠ PEDIDO_ITENS      — criada, 0 linhas (tabela    ││
│  │                        vazia na origem)            ││
│  │ ✅ V_CLIENTES_ATIVOS — view criada                 ││
│  │ ❌ LOG_EXPORTACAO    — ignorada (não selecionada)  ││
│  └─────────────────────────────────────────────────────┘│
│                                                         │
│  [ 🔄 Nova Migração ]  [ ✅ Fechar ]                   │
└─────────────────────────────────────────────────────────┘
```

---

## 5. Interação do Usuário para Correção de Mapeamentos

### 5.1 O que o sistema NÃO consegue resolver sozinho

| Situação | Motivo | O que o usuário vê |
|---|---|---|
| Firebird `BLOB SUB_TYPE 0` (binário) | Pode ser imagem, PDF, bytecode | ⚠ Alerta: "Tipo binário — verificar necessidade" |
| Oracle `NUMBER` sem precisão | Pode ser inteiro ou decimal | Dropdown: `BIGINT` / `DECIMAL(38)` / `NUMERIC` |
| `CHAR(1)` como booleano | Convenção de domínio | ⚠ Sugestão: converter para `BOOLEAN`? |
| Trigger de auto-increment Firebird | Lógica de negócio embutida | Mostra trigger original, usuário decide se converte |
| View complexa com sintaxe proprietária | `sqlglot` pode não conseguir transpilar | ❌ Vermelho: "Requer revisão manual" |
| Sequence sem nome padronizado | Nome pode conflitar | ⚠ Alerta de conflito |
| Campos `COMPUTED BY` (Firebird) | Expressão pode não ter equivalente | Mostra expressão original, usuário reescreve |
| Oracle `SYNONYM` | Sem equivalente no destino | ❌ Ignorado com aviso |

### 5.2 Fluxo de Correção na Tela 4 (Mapeamento)

```
                    ┌──────────────────┐
                    │  Usuário vê um   │
                    │  tipo não mapeado│
                    │  ou alerta ⚠     │
                    └────────┬─────────┘
                             │
                             ▼
              ┌──────────────────────────┐
              │  Clica no campo "Destino" │
              │  da coluna problemática   │
              └────────┬─────────────────┘
                       │
                       ▼
        ┌──────────────────────────────────┐
        │  Dropdown ou diálogo de edição    │
        │                                   │
        │  Tipo atual: BLOB (Firebird)     │
        │  ▼ Destino:                       │
        │  ○ BYTEA     (recomendado)       │
        │  ○ TEXT                          │
        │  ○ VARCHAR(8192)                 │
        │  ○ [Personalizado...]            │
        │                                   │
        │  ☐ Aplicar para todas colunas    │
        │     com este tipo                 │
        │                                   │
        │        [ OK ]    [ Cancelar ]    │
        └──────────────────────────────────┘
                       │
                       ▼
          ┌──────────────────────────┐
          │  Tabela atualizada com   │
          │  o tipo escolhido        │
          │  (sem ícone de alerta)   │
          └──────────────────────────┘
```

### 5.3 Personalização Avançada

O usuário pode clicar com botão direito em qualquer linha e escolher:

- **Editar expressão CAST** → abre editor de texto para definir conversão customizada
- **Ignorar coluna** → coluna não é criada no destino
- **Adicionar coluna extra** → insere coluna no destino (ex: `criado_em TIMESTAMP`)
- **Renomear coluna/tabela** → altera nome no destino
- **Salvar mapping como template** → reutilizar em migrações futuras do mesmo cliente

### 5.4 Templates de Mapping

O usuário pode salvar um arquivo JSON com overrides:

```json
{
  "template_name": "Cliente ACME - Firebird para PG",
  "source": { "type": "firebird", "version": "2.5" },
  "target": { "type": "postgresql", "version": "16" },
  "overrides": {
    "CLIENTES": {
      "ID_CLIENTE": { "target_type": "UUID", "default": "gen_random_uuid()" },
      "OBSERVACAO": { "target_type": "VARCHAR(500)" }
    },
    "global": {
      "BLOB": { "target_type": "TEXT" }
    }
  }
}
```

---

## 6. Cronograma Estimado de Implementação

| Fase | Componentes | Esforço |
|---|---|---|
| **1** | Expandir `ColumnInfo`, criar `FullSchema`, `SequenceInfo`, `TriggerInfo`, `ViewInfo` | 2 dias |
| **2** | Implementar extração estendida em cada adapter (MSSQL, Oracle, Firebird) | 4 dias |
| **3** | Criar tabelas de mapeamento de tipos (Firebird→PG, Oracle→MariaDB, MSSQL→PG, etc.) | 3 dias |
| **4** | Implementar `TypeConverter` com regras de conversão e detecção de conflitos | 3 dias |
| **5** | Implementar gerador de script DDL no dialeto destino | 2 dias |
| **6** | Criar wizard UI (6 telas) — `ui/migration_dialog.py` | 5 dias |
| **7** | Implementar execução da migração + logs | 2 dias |
| **8** | Salvamento/carregamento de templates de mapping | 1 dia |
| **9** | Testes com bancas reais e ajustes | 3 dias |
| | **Total** | **~25 dias** |

---

## 7. Decisões de Arquitetura

| Decisão | Opção Escolhida | Motivo |
|---|---|---|
| **Biblioteca de transpilação SQL** | `sqlglot` (já existe) | Usar apenas para views e expressões; DDL é gerado por código |
| **Mapper de tipos** | Tabelas declarativas em Python | Mais legível e fácil de estender que XML/JSON externo |
| **Executor de migração** | Transação única ou por tabela | Usuário escolhe: "tudo ou nada" vs "continua com erros" |
| **Migração de dados** | `SELECT *` em lotes → `INSERT` | Evita carregar tudo em memória |
| **Templates** | JSON versionável | Pode ser compartilhado entre equipes |
