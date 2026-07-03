# Subagentes Especializados

Este documento registra os subagentes especializados disponíveis neste projeto, conforme diretriz do `AGENTS.md`.

## Propósito

Subagentes são agentes com habilidades específicas que devem ser utilizados para:
- Pesquisa e exploração de código
- Revisão técnica de arquitetura, banco de dados, código, segurança e desempenho
- Implementação de alterações no código-fonte
- Elaboração de documentação

## Lista de Subagentes

| Subagente | Especialidade | Quando usar |
|-----------|---------------|-------------|
| `firebird-sql` | Firebird 2.5, 3, 4 e 5 — procedures, triggers, otimização | Consultas Firebird, migração de objetos, tuning |
| `mssql` | SQL Server — T-SQL, procedures, índices, tuning | Consultas MSSQL, migração, tuning |
| `oracle-sql` | Oracle Database — tuning, procedures, views, consultas complexas | Consultas Oracle, migração, tuning |
| `python-fastapi` | Backend moderno com Python e FastAPI | Criação de APIs REST, endpoints, validações |
| `supabase` | PostgreSQL, autenticação e storage com Supabase | Migração para Supabase, queries PostgreSQL |
| `fullstack-brasil` | Orquestrador principal para projetos corporativos brasileiros | Projetos que integram Delphi, Python, bancos de dados |
| `delphi-expert-master` | Delphi 12 — VCL/FMX, migração de legados (Delphi 7/XE7) | Desenvolvimento Delphi, migração de sistemas |
| `arquiteto-software` | Arquitetura de software, DDD, Clean Architecture, modelagem | Definição de arquitetura, modelagem de sistemas |
| `auditor` | Verificação de alucinações e suposições | Revisão de respostas antes de implementar |
| `revisor-tecnico` | Revisão de arquitetura, banco, código, segurança, desempenho | Code review, auditoria técnica |
| `contabilidade-br` | Sistemas contábeis, financeiro, plano de contas, integração fiscal | Regras contábeis/fiscais brasileiras |
| `ui-brasil` | Padrões visuais brasileiros para sistemas corporativos | Design de interfaces para mercado brasileiro |
| `frontend-design` | Direção estética visual, tipografia, design intencional | Quando o design precisa ser diferenciado, não genérico |
| `ai-sdk` | AI SDK — agentes, chatbots, RAG, tool calling, structured output | Funcionalidades com IA generativa |
| `nextjs` | Next.js App Router — routing, Server Components, Server Actions | Desenvolvimento Next.js |
| `shadcn` | Gerenciamento de componentes shadcn/ui | Adicionar/configurar componentes shadcn |
| `animate` | Animações, transições, hover effects, page transitions | Implementar animações em componentes React |
| `lovable-builder` | Criação de sistemas completos na plataforma Lovable | Projetos na plataforma Lovable |

## Regras de Uso

1. **Sempre delegar** implementação de código para subagentes especializados.
2. **Nunca implementar** código diretamente — o coordenador apenas coordena e audita.
3. **Subagentes de pesquisa** (`explore`) devem ser usados para explorar codebase antes de implementar.
4. **Subagentes de revisão** (`auditor`, `revisor-tecnico`) devem ser usados para validar planos e resultados.
5. Ao delegar, especificar claramente:
   - Qual subagente usar
   - Qual tarefa executar
   - Quais arquivos modificar
   - Qual o resultado esperado

## Fluxo de Trabalho

1. Planejar dividindo o trabalho em tarefas paralelizáveis
2. Exibir os subagentes que serão utilizados e para quais tarefas
3. Delegar cada tarefa para um subagente especializado
4. Auditar o resultado entregue pelo subagente
5. Executar testes, lint e type check para validar
6. Reportar ao usuário o que foi feito
