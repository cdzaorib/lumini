# Registro de tarefas

Atualizar após cada tarefa concluída/bloqueada e apontar detalhes em arquivos próprios.

| ID | Tarefa | Estado | Evidência |
|---|---|---|---|
| T01 | Criar plano, decisões e instruções de continuidade | Concluída | `PLANO.md`, `DECISOES.md`, `AGENTS.md`, `CLAUDE.md`; pasta inicial inspecionada vazia |
| T02 | Fundação backend Python/FastAPI | Concluída | `../backend/FOUNDATION_REPORT.md`: 24 testes, Ruff, mypy, lock e migração offline |
| T03 | Fundação frontend Next.js | Concluída | `../frontend/FOUNDATION_REPORT.md`: instalação limpa, lint, typecheck, build, HTTP e audit0 |
| T04 | Ambiente local, checks e CI | Concluída | 24 unitários + 14 integrações reais PostgreSQL/Redis; CI preparado, não executado remotamente |
| T05 | Sessão Claude, Remote Control e IDE | Concluída com limite de UI | Claude conectado/RC ativo; PyCharm 2026.2.3 instalado/iniciado; primeiro uso e seleção do interpretador não verificados |
| T06 | Revisão integrada e handoff final do marco | Concluída | TLS/traceback corrigidos; 30 unitários+14 integrações; evidências em `VALIDACAO-001.md` |
| T07 | Autorização administrativa e aprovação do catálogo | Próxima | Google login atrás de adapter; testes sintéticos; validar real quando houver conta de teste |
| T08 | Reservas transacionais e contrato de calendário | Planejada | Estados, idempotência/outbox, expiração/sinal e testes concorrentes antes de Google real |
| T09 | PoC Evolution e modo humano | Dependente de instância de teste | Provar origem das mensagens; invalidar respostas pendentes; sem número real por enquanto |
| T10 | IA, experiência pública e piloto | Planejada | Seguir fases 4–6 do plano e seus gates |

## 2026-10-01 — T01

Plano aprovado consolidado em arquivo; instruções carregáveis pelo Claude; separação entre progresso local/mock e integrações reais; obrigação de atualizar handoff a cada tarefa. Python substitui Node no backend. Nenhuma alteração no Tecnoarte.

## 2026-10-01 — T05, sessão Claude

VS Code aberto na pasta Lumini. Claude CLI autenticado e iniciado com `--remote-control Lumini --no-chrome --ide`. Terminal confirmou Remote Control ativo; `/ide` mostrou VS Code conectado e lock da extensão referenciou a pasta Lumini. Sessão mantida ociosa para o usuário; sem solicitar implementação paralela ao Claude. URL remota omitida de arquivos versionados.

## 2026-10-01 — Revisão de arquitetura

Revisão independente somente leitura incorporada em ADR-007 a ADR-009: contexto permitido para IA, estados de reserva, revalidação do modo humano antes de enviar, retenção separada e orçamento ainda não validado. Não equivale a implementação nem a teste das integrações.

## 2026-10-01 — T02 e T03

Os dois agentes encerraram suas edições. Backend tem API de saúde, conexões lazy PostgreSQL/Redis, esquema/migração de catálogo e worker configurado sem jobs. Frontend tem prévia interna estática com link ao site atual, robots restritivo, acessibilidade básica e headers. Relatórios de cada componente registram comandos, versões, resultados e limites. Check adicional do coordenador com banco/Redis reais temporários e navegador está em andamento; não há autorização/login/agendamento funcional ainda.

## 2026-10-01 — T04

Testes opt-in adicionados e executados em PostgreSQL15.19 e Redis7.0.15 locais isolados: **14 passaram**; 24 unitários também passaram. Suítes deselecionadas explicitamente por marker, nenhum skip silencioso. Inserts sintéticos revertidos (três tabelas de catálogo vazias ao final). Ruff/mypy/lock verdes. Migração upgrade/check e readiness real comprovados. CI com serviços sintéticos preparado, execução GitHub não realizada. Evidências do navegador em `VALIDACAO-001.md`.

## 2026-10-01 — T05, PyCharm

PyCharm2026.2.3 baixado de JetBrains, checksum oficial SHA256 validado, paths do tar inspecionados e extraído em diretório novo do usuário. Launcher `~/.local/bin/pycharm-lumini` e desktop entry criados. Processo iniciado com pasta Lumini como argumento. Não foram aceitos termos/licença/telemetria nem configurada conta; seleção do interpretador pela UI permanece para o primeiro uso. Ambiente Python está pronto em `backend/.venv/bin/python`.

## 2026-10-01 — T06 concluída

Worker real respondeu `pong` via Redis. Migração roundtrip no banco efêmero passou, sem drift. Falhas de default TLS e traceback de construção corrigidas e cobertas por regressões. Resultado final: **30 unitários + 14 integrações reais locais**, Ruff/mypy/formatação/lock verdes; frontend lint/typecheck/build e navegador aprovados. Nenhuma credencial real envolvida. API, worker e serviços efêmeros encerrados; frontend/Claude/PyCharm preservados. Primeiro marco pronto para commit local; sem push/deploy.
