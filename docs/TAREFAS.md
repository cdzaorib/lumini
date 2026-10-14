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
| T07 | Autorização administrativa e aprovação do catálogo — backend | Concluída (real local; Google não validado) | 117 unitários + 55 integrações PostgreSQL/Redis locais; migração 0002 roundtrip sem drift; `API-ADMIN.md`, ADR-010/011 |
| T07b | Painel administrativo do catálogo (frontend + Google Identity Services) | Concluída (real local; Google real não validado) | `VALIDACAO-002.md`: E2E 12/12 no Chrome, CSP 0 violações (stub e script real), build de produção; 121 unitários + 55 integrações |
| T07c | Verificação de segredos no CI (Fase 1 do plano integral) | Concluída (local; CI não executado remotamente) | gitleaks 8.30.1, checksum oficial conferido; histórico limpo; controle positivo detectou token falso |
| T08a | Núcleo de reservas (estados, trava, sinal, expiração, cancelamento, reagendamento, outbox) | Concluída (real local; calendário fake) | Migração 0003; 130 unitários + 91 integrações (33 de fluxo, 3 de concorrência real com commits); ADR-013 |
| T08b | API administrativa e painel de reservas/agenda | Concluída (real local; calendário fake) | `VALIDACAO-003.md`: 152 unitários + 119 integrações; E2E 26/26 no Chrome, CSP 0; ADR-014; corrigida leitura desatualizada no núcleo |
| T08c | Worker (Celery beat), adaptador Google Calendar e reconciliação | Concluída (real local; Google simulado) | `VALIDACAO-004.md`: 194 unitários + 127 integrações; worker real com beat executou o tick; ADR-015 |
| T08d | Autoatendimento por link seguro (cancelar/reagendar) | Concluída (real local) | `VALIDACAO-005.md`: 211 unitários + 140 integrações (20 rodadas estáveis); E2E cliente 18/18 e painel 26/26; ADR-016; corrigido deadlock intermitente da T08a |
| T09 | WhatsApp (Evolution), modo humano e avisos | Concluída (real local; Evolution simulada — PoC real pendente) | `VALIDACAO-006.md`: 238 unitários + 161 integrações (10 rodadas); E2E integrações 12/12, painel 26/26, cliente 18/18; ADR-017; `RUNBOOK-WHATSAPP.md` |
| T10 | IA, experiência pública e piloto | Concluída (real local; provedores simulados; lançamento pendente) | `VALIDACAO-007.md`: 285 unitários + 180 integrações; E2E site 17/17, chat 16/16 + regressões; backup/restauração ensaiados; `LANCAMENTO.md` com o estado de cada gate; ADR-018 |
| T11 | Itens restantes do plano só com código (conteúdo do site no painel, métricas, comparecimento, alerta de sobreposição, E2E versionado, revisões) | Concluída (real local) | `VALIDACAO-008.md`: 299 unitários + 189 integrações; `make e2e` 7/7 (111 etapas); `SEGURANCA.md`; deploy segue exigindo autorização específica |

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

Worker real respondeu `pong` via Redis. Migração roundtrip no banco efêmero passou, sem drift. Falhas de default TLS e traceback de construção corrigidas e cobertas por regressões. Resultado final: **30 unitários + 14 integrações reais locais**, Ruff/mypy/formatação/lock verdes; frontend lint/typecheck/build e navegador aprovados. Nenhuma credencial real envolvida. API, worker e serviços efêmeros encerrados; frontend/Claude/PyCharm preservados. Primeiro marco salvo no commit local `ccff572`; sem push/deploy. Revisão de arquivos staged: sem diretórios locais/segredos incluídos e sem padrões conhecidos de tokens/chaves privadas; não equivale a auditoria de segurança exaustiva.

## 2026-10-01 — T07 backend concluído (Claude, retomando Codex)

Codex atingiu limite de uso às 11:00–11:02 (volta em 2026-10-04 17:40) com T07 parcial: auth, schemas, migração 0002 e testes de integração escritos, mas sem `catalog/router.py`, sem serviço de domínio e sem ligação no app (suíte não coletava; lint/mypy falhando). Confirmado pelos logs da sessão Codex que nenhum agente seguia gravando antes da retomada.

Implementado: `lumini/catalog/service.py` (regras: trava advisory, revisão otimista, aprovação por profissional/revisão, invalidação por edição/credencial, publicação revalidada, catálogo público revalidado, auditoria só com IDs/sub), `lumini/catalog/router.py` (auth em nível de router antes da sessão, erros fixos 403/404/409/503, `no-store`), `app.py` (settings/verificador em `app.state`, handler 422 sem eco de entrada, CORS GET/POST/PATCH+Authorization sem credenciais). Ajustes: `services.approved_by` 255 (sub completo), tolerância de 10s para `iat`/`nbf`, chamada tipada ao google-auth, PublicProfessional sem registro de conselho, `as const` em decoders do frontend.

Testes novos: `tests/test_auth.py` (47) com tokens RS256 assinados por chaves sintéticas geradas no teste e certificados servidos por fake de `requests.get` — assinatura alheia, payload adulterado, aud/iss/exp/iat/nbf/email_verified/hd inválidos, allowlist 403, revogação na próxima requisição, falha fechada sem configuração, falhas de certificado = 503, cache por `max-age`, sem eco de token/exceção. Integração: 15 novos casos (trava advisory provada com segunda conexão, referências desconhecidas, slug duplicado, completude/preço/sinal, idempotência, 404, PATCH sem mudança).

Evidência: `make backend-check` verde (Ruff, format, mypy strict 28 arquivos, **117 unitários**); `pytest -m integration -W error` com PostgreSQL 15.19/Redis 7.0.15 locais sintéticos: **55 passaram**, zero warnings/skips; tabelas vazias e nenhuma trava advisory remanescente ao final. Alembic upgrade→downgrade 0001→upgrade e `alembic check` sem drift no banco `lumini_foundation_test`. Frontend: ESLint e typecheck verdes; **`next build` não executado** para não sobrescrever `.next` do preview em execução na porta 3000 (os arquivos alterados não são importados por página). Mock/não validado: Google real, painel, deploy. Mudanças **não commitadas** (aguardando o usuário).

## 2026-10-01 — Plano integral registrado

Usuário reafirmou que o plano do grill-me é o escopo, com a única troca do backend para Python/FastAPI. Texto integral em `PLANO-ORIGINAL.md`; `PLANO.md` ganhou a lista “Itens do plano integral a não perder” (evento temporário no calendário, fallback do modo humano, restrições de comunicação, publicidade de enfermagem, verificação de segredos no CI, critérios de lançamento extras). Commits locais: `32f4074` (T07) e `f516669` (plano).

## 2026-10-01 — T07b painel concluído (Claude)

Implementado: `/admin` (`src/app/admin/{page,admin-app,professionals,services,ui}.tsx`), login Google Identity Services com token só em memória, cadastro/edição/verificação/revogação de profissionais, cadastro/edição de procedimentos com todos os campos da matriz, pendências de aprovação espelhando o backend, aprovação com confirmação explícita por profissional atribuída, publicação/despublicação, mensagens em PT-BR, foco preservado após ações que removem o próprio botão. `src/proxy.ts`: CSP com nonce só em `/admin` (ADR-012). Backend: campo `communication_restrictions` (interno, nunca público); registro de conselho de profissionais verificadas passou a ser público (Cofen 554/2017, revisão da ADR-011); corrigido limite de categoria do procedimento (schema aceitava 160, coluna tem 120 → 503 em vez de 422). `frontend/AGENTS.md`/`CLAUDE.md` gerados pelo `next dev` foram versionados.

Evidência em `VALIDACAO-002.md`. A prévia da porta 3000 (antes iniciada pelo Codex) foi parada, reconstruída e religada por esta sessão. Ambiente E2E (banco `lumini_e2e_test`, backend de teste, scripts Playwright) ficou fora do Git e foi removido. Não validado: login Google real, HTTPS/deploy, CSP da landing, suíte E2E versionada.

## 2026-10-01 — T07c verificação de segredos

Job `secrets` no CI baixa gitleaks 8.30.1 do release oficial, confere SHA-256 (`551f6fc8…70eb`, igual ao `checksums.txt` publicado) e varre todo o histórico (`fetch-depth: 0`) com `--redact`. `make secrets-check` faz o mesmo localmente (binário verificado copiado para `.tools/bin/`, ignorado pelo Git) e passou a abrir `make check`. Local: 5 commits sem vazamentos. Controle positivo em repositório temporário com token falso no formato do GitHub: detectado, saída 1. YAML do workflow validado por parser. CI remoto não executado (sem remoto Git).

## 2026-10-01 — T08a núcleo de reservas (Claude)

Implementado em `backend/src/lumini/booking/`: `policy.py` (regras como dados), `availability.py` (cálculo puro de horários), `calendar.py` (contrato do adaptador, ids determinísticos), `service.py` (disponibilidade, reserva idempotente, sincronização com calendário, confirmação humana do sinal, expiração, cancelamento, reagendamento, resolução de conflito, agendamento de mensagens), `outbox.py` (enfileirar/arrendar/concluir/backoff) e `dispatch.py` (`tick`: expira, agenda mensagens, entrega outbox revalidando relevância). Migração `0003_bookings` (contatos, agenda e regras semanais, reservas com `EXCLUDE` gist, eventos de auditoria, outbox). Catálogo: elegibilidade pública extraída para `bookable_service`, reutilizada pela reserva. `tzdata` adicionado.

Evidência: `make backend-check` verde (Ruff, mypy strict 40 arquivos, **130 unitários**); integração com `-W error` **91 passaram**, incluindo 33 de fluxo e 3 de concorrência real em conexões separadas com commit (8 reservas simultâneas no mesmo horário → exatamente 1; 6 repetições da mesma chave → 1 reserva; corrida sinal × expiração em 6 reservas → nunca as duas), repetidos 5 vezes sem instabilidade; dados sintéticos removidos ao final (tabelas zeradas). Migração 0003: upgrade → downgrade → upgrade e `alembic check` sem drift. Calendário é **fake** (`tests/booking_fakes.py`); Google real, worker agendado, API e painel ainda não existem.

## 2026-10-05 — T08b API e painel de agenda/reservas (Claude)

Retomada de trabalho não commitado da sessão Claude anterior (interrompida em 2026-10-01 13:02, logo após o commit da T08a): códigos de erro estáveis em `BookingError`, `lumini/deps.py` (sessão, relógio e calendário compartilhados; catálogo passou a usá-lo), `booking/schemas.py` e `booking/schedule.py`. Conferido antes: nenhum agente gravando (Codex ativo no VS Code só importou a sessão anterior; arquivos parados desde 01/10). A máquina reiniciou: PostgreSQL/Redis de teste e a prévia na porta 3000 tinham sumido e foram recriados.

Implementado: `booking/router.py` (agenda GET/PUT, prévia de horários, lista `upcoming|history`, detalhe, sinal, cancelamento, conflito, reagendamento; respostas `{detail, code}`), `booking/queries.py` (views da equipe com contato), troca de `calendar_id` bloqueada com reservas dependentes, faixas na grade de 15 min, `CalendarNotConfigured` → 503 `calendar_not_configured`, CORS com `PUT`. Painel: abas Reservas/Agenda/Catálogo (`admin/bookings.tsx`, `admin/agenda.tsx`, `lib/admin/schedule.ts`), lista de rotas permitidas no cliente ampliada só com caminhos exatos, mensagens PT-BR por código, horários sempre em Brasília.

Defeito do núcleo T08a corrigido (ADR-014): leituras sem trava devolviam a cópia da reserva já carregada na sessão (`expire_on_commit=False`); um worker com sessão longa marcaria cancelamento como "sem mudança" e enviaria mensagens obsoletas. Regressão com controle negativo.

Varredura de segredos do histórico estava vermelha desde a T08a por falso positivo (chave de idempotência sintética); registrado em `.gitleaksignore` por impressão digital exata, com controle positivo. Commits locais `c846947` (T08b) e seguinte (`.gitleaksignore` + docs).

Evidência em `VALIDACAO-003.md`. Real local: API + PostgreSQL + painel no Chrome. Mock: identidade, calendário (em memória), script do Google. Não iniciado: adaptador Google, worker agendado, mensagens.

## 2026-10-05 — T08c worker, adaptador Google e reconciliação (Claude)

Implementado: `booking/google_calendar.py` (REST v3, conta de serviço, `requests` em threads, classificação de falhas sem texto do Google, upsert PUT/POST, delete idempotente), `booking/reconcile.py` (reenfileirar sincronizações travadas; reparar eventos da Lumini alterados no Google), `booking/jobs.py` (ciclos com engine própria e trava Redis), tarefas e beat em `worker.py`, `LUMINI_GOOGLE_CALENDAR_CREDENTIALS` validada em `settings.py`, `app.state.calendar` montado a partir dela. `tick` aceita rodar sem calendário (só expira e agenda mensagens). Identificação estrita dos eventos da Lumini. Outbox informa se gravou o job e aceita motivo na chave de deduplicação.

Evidência em `VALIDACAO-004.md`. Real local: worker Celery + beat + PostgreSQL + Redis. Mock: Google (transporte HTTP falso, calendário em memória). Não iniciado: credencial real, envio de mensagens, alerta de sobreposição de terceiros em reserva confirmada.

## 2026-10-05 — T08d autoatendimento por link (Claude)

Usuário pediu para seguir até a etapa 10. Implementado: `booking/links.py` (token HMAC), `booking/public_router.py` (ver, horários, cancelar, reagendar com ator `client`), `ratelimit.py`, `POST /api/admin/bookings/{id}/manage-link`, configurações `LUMINI_MANAGE_LINK_SECRET`/`LUMINI_PUBLIC_SITE_URL`, regras de autoatendimento extraídas para funções únicas. Frontend: página `/reserva` (token no fragmento, CSP por nonce, `no-referrer`, `noindex`), botão “Link de autoatendimento” no painel, formatadores de horário compartilhados em `lib/clinic-time.ts`, origem da API compartilhada em `lib/api-origin.ts`.

Defeitos encontrados e corrigidos: deadlock intermitente em reservas simultâneas (T08a; repetição da transação, regressão determinística + 20 rodadas verdes); página não reagia a outro link aberto na mesma aba; dia da semana com maiúsculas em todas as palavras.

Evidência em `VALIDACAO-005.md`. Real local: API pública + PostgreSQL + Redis + página no Chrome. Mock: calendário em memória, identidade do painel. Não iniciado: envio automático do link (T09).

## 2026-10-05 — T09 WhatsApp e modo humano (Claude)

Sem instância de teste: construído e validado com webhooks simulados e remetente falso; documentação da Evolution consultada (formato do envio e do webhook; mensagens da API chegam como `messages.upsert` `fromMe`). Implementado: migração `0004_whatsapp` (conversas, metadados de mensagens, estado de integração), `lumini/whatsapp/` (cliente Evolution, webhook autenticado, registro idempotente, modo humano com `#bot`/`#pausa`, envio revalidado por modo/versão, fluxo numérico até a reserva, notifier do outbox com link da T08d, reenvio após queda), worker integrado (classificação, avisos, reenvio, varredura), aba “Integrações” e aviso de desconexão no painel, `RUNBOOK-WHATSAPP.md`.

Defeitos/ajustes encontrados durante a validação: webhook recusado ainda resolvia a dependência de banco (autenticação passou a ser a primeira dependência); relógio do banco misturado ao da aplicação em carências (horários gravados explicitamente); equipe respondendo durante um envio do bot demorava até 2 min para pausar o bot (agora pausa ao fim do envio).

Real local: webhook + PostgreSQL + worker + painel no Chrome. Mock: Evolution (remetente falso, payloads simulados), calendário em memória. Não validado: instância real (PoC listada no runbook), números com/sem nono dígito e `@lid` reais, entrega real de mensagens.

## 2026-10-05 — T10a camada de IA (Claude)

`lumini/ai/`: redação de identificadores, contratos estruturados, cliente OpenAI-compatível (DeepSeek), assistente com validação de saída e contabilidade sem texto, guardrails do redator, bancada sintética (`python -m lumini.ai.benchmark`, não executada: sem chave). Integrado ao fluxo do WhatsApp só para texto livre nos passos de navegação; **desligado por padrão** (ADR-018). Migração `0005_leads_ai` (contabilidade de IA e tabela de leads usada na T10b). Evidência: 267 unitários + 165 integrações (3 rodadas); testes de rota por confiança, redação antes de sair, modelo nunca consultado em nome/confirmação, respostas checadas e contabilidade sem texto. Mock: provedor (cliente roteirizado). Não iniciado: benchmark real, Jev.

## 2026-10-05 — T10b pedidos de contato (Claude)

`lumini/leads/`: formulário público com consentimento de contato obrigatório e de marketing separado, sem texto livre, armadilha de robô, deduplicação diária, limite por endereço; lista e status no painel (aba “Contatos”, link para WhatsApp); exclusão automática dos não convertidos após 90 dias no tick. Evidência: 18 unitários + 8 integrações. Validação no navegador junto com o site (T10c).

## 2026-10-05 — T10c site público (Claude)

Landing (`/`) a partir do catálogo publicado: hero do plano, áreas, procedimentos com preço só pela regra (valor, “a partir de” ou após avaliação), como funciona, profissionais verificadas com registro (Cofen), políticas de agendamento geradas das regras do sistema, formulário de contato; página por procedimento (`/procedimentos/[slug]`); privacidade e termos como **rascunhos** (sem indexação, aviso visível); `robots`/`sitemap`/`X-Robots-Tag` fechados até `LUMINI_SITE_PUBLIC=true`; CSP por nonce em todas as páginas; conteúdo da clínica em `frontend/src/content/site.ts` com pendências visíveis só na prévia (`LUMINI_SITE_STAGE=production` oculta). Nada inventado: endereço, horários, WhatsApp, diferenciais, perguntas frequentes, fotos e depoimentos aguardam a clínica. Sem analytics/pixel.

Evidência: E2E no Chrome 17/17 (site + formulário + aba Contatos), lint e typecheck verdes.

## 2026-10-05 — T10d chat no site (Claude)

`lumini/webchat/`: sessão por token aleatório (servidor guarda só o hash), mesmo fluxo do WhatsApp (e IA, se ligada), passo de WhatsApp com aviso de uso antes de reservar, pedidos de equipe/saúde encaminhados ao formulário (ninguém acompanha o chat ao vivo), nenhum texto da pessoa gravado, limites por endereço e por sessão, sessões apagadas um dia após o início. Frontend: componente de conversa com respostas rápidas, página `/atendimento` (com formulário de contato) e botão flutuante na landing; ícone do site.

Defeitos encontrados: token inválido ainda abria sessão de banco (checagem virou a primeira dependência); limpeza de sessões não apagava porque atribuir o mesmo valor a `updated_at` deixa o banco aplicar o próprio relógio (passou a usar `created_at`); orientação “Fale com a clínica nesta página” sem formulário em `/atendimento`; `favicon` 404.

Evidência: 7 integrações novas; E2E chat 16/16 e regressão site 17/17, painel 26/26, cliente 18/18, integrações 12/12.

## 2026-10-05 — T10e piloto: backup e checklist (Claude)

Scripts `infrastructure/backup/backup.sh` e `restore.sh` (checksum, permissões restritas, recusa de destino não vazio ou igual à origem) e ensaio completo local (`VALIDACAO-007.md`); `RUNBOOK-BACKUP.md`; `LANCAMENTO.md` com cada critério do plano e seu estado real. Encerra o pedido do usuário de seguir até a etapa 10: tudo o que dependia só de código está construído e testado localmente; o restante depende da clínica, de credenciais ou de autorização de publicação.

## 2026-10-05 — T11a conteúdo do site pelo painel (Claude)

Usuário pediu para continuar até o final. Sem autorização de deploy, seguem os itens do plano integral que dependem só de código. Implementado: migração `0006_site_settings` (linha única versionada; auditoria `site`), `lumini/site/` (endereço, horários, WhatsApp, Instagram, diferenciais, perguntas frequentes, depoimentos só com autorização registrada, contato de privacidade, instruções do sinal) com regra de publicidade (sem promessa de resultado/antes e depois), API pública sem instruções do sinal nem registros de autorização; bot envia as instruções reais do sinal quando preenchidas. Frontend: aba “Site” no painel; landing, rodapé e páginas legais leem o conteúdo da API (cache 60 s), botão de WhatsApp, mapa, depoimentos e dados estruturados de negócio local com nonce; `frontend/src/content/site.ts` ficou só com identidade e portões.

Evidência: 12 unitários + 4 integrações novos; E2E conteúdo 12/12, site 17/17, painel 26/26.

## 2026-10-05 — T11b resumo, comparecimento e histórico (Claude)

Migração `0007_attendance`: comparecimento (`attended`/`no_show`, só reservas confirmadas e depois do início, com versão e auditoria); reserva com comparecimento não pode ser cancelada nem reagendada; recomendações pós-procedimento não vão para quem faltou; `booking_events.created_at` passou a `clock_timestamp()` (com `now()`, eventos gravados na mesma transação empatavam e o histórico saía fora de ordem). Origem da reserva pelo canal (WhatsApp, chat do site, reagendamento). Métricas do plano (§11) em `GET /api/admin/metrics?days=`: pedidos de contato, reservas, sinais, atendimentos, comparecimentos, faltas, cancelamentos, reagendamentos, expirações, procura por procedimento, origem, conversas passadas à equipe. Painel: aba “Resumo” (indicadores e tabelas, sem cores carregando significado), botões “Compareceu/Faltou” e “Histórico” em cada reserva.

Evidência: 4 integrações novas (188 no total, 2 rodadas); E2E resumo 10/10, painel 26/26, cliente 18/18.

## 2026-10-05 — T11c aviso de sobreposição no Google (Claude)

Migração `0008_calendar_overlap`. A reconciliação (a cada 15 min) marca reservas aguardando sinal ou confirmadas que têm outro compromisso no Google no mesmo horário, registra no histórico, desmarca quando o compromisso sai e não altera a reserva (ADR-015 atualizada). Painel mostra o aviso no cartão da reserva. Evidência: integração nova (reconciliação 9/9); sem E2E de navegador (a reconciliação roda no worker, não no cenário E2E).

## 2026-10-05 — T11d cenários de navegador versionados (Claude)

Os roteiros que viviam no scratchpad agora estão em `e2e/`: `server.py` (API real sobre banco `lumini_e2e_test` recriado e migrado a cada cenário; recusa banco não local), 7 cenários parametrizados, `run.mjs` (sobe API e `next dev`, roda tudo, derruba só o que criou, código de saída 1 em falha), `package.json`/lockfile com `playwright-core` 1.63.0 fixo, `README.md` e `make e2e`. Capturas em `e2e/.output/` (fora do Git).

Evidência: `make e2e` com os 7 cenários aprovados — painel 26/26, autoatendimento 18/18, integrações 12/12, site 17/17, chat 16/16, resumo 10/10, conteúdo 12/12 (111 etapas) — e portas liberadas ao final.

## 2026-10-05 — T11e revisão de interface e segurança (Claude)

Revisão pelas Web Interface Guidelines nas telas da cliente (site, chat, reserva) com 13 ajustes aplicados (lista em `VALIDACAO-008.md`). Segurança: `docs/SEGURANCA.md` (superfície pública e controles) e `backend/tests/test_route_guards.py` (toda rota administrativa recusa anônimo com 401; rotas públicas = lista revisada). `make e2e` 7/7 depois das mudanças. Encerra a etapa 11: o que resta depende de conteúdo da clínica, contas/credenciais e autorização de publicação.

## 2026-10-06 — T12 preparação de produção (Codex; publicação bloqueada)

Auditoria antes de alterações: `main` limpa em `9ea0aa7`, 22 commits, sem remote; Next.js 16.3.8/React 19.3.0/TypeScript/Tailwind no frontend, FastAPI/Python 3.12/SQLAlchemy/Alembic/Celery/Redis no backend. Nenhuma integração Supabase existente. Usuário confirmou manter FastAPI/login Google, usar Supabase PostgreSQL, Railway API/worker/Redis; autorizou criar repo GitHub público e push. Código/dependências/lockfiles intactos.

Arquivos: `.gitignore` (ignora `.vercel/`), `frontend/vercel.json`/`.vercelignore`, `backend/railway.api.json`/`railway.worker.json`, `docs/DEPLOY.md` (auditoria, nomes de variáveis, instruções exatas de painel/Google/domínio e bloqueios), `docs/DECISOES.md` (ADR-019), `infrastructure/README.md`, `docs/LANCAMENTO.md` e este handoff. Migrações não foram alteradas/aplicadas na nuvem; nenhum segredo criado em arquivo.

**Real na nuvem:** criado Vercel `lumini` (`prj_QLNtFWbhZcQbEY9xic5IqnMOZoVY`) na equipe `cdzaoribs-projects`; raiz `frontend`, Next.js, Node 22.x, install `npm ci`, build `npm run build`, output automático. Configuradas só `LUMINI_SITE_STAGE` e `LUMINI_SITE_PUBLIC` em Production/Preview. Nenhum deployment, domínio de produção ou vínculo Git ainda.

**Validação real local:** `npm ci` com Node 22.23.2, lint, typecheck e build passaram; Ruff check/format (98 arquivos), mypy (96 arquivos), `pytest -W error` 299/299 e integração PostgreSQL/Redis com `-W error` 189/189; E2E final `node run.mjs` em cópia isolada **7/7 cenários, 111/111 etapas** (painel/logout, autoatendimento, integrações, site/contato, chat, métricas, conteúdo). CSP e console verdes na rodada final; dados/login/agenda/Evolution sintéticos. `uv sync --frozen --no-dev` em cópia independente instalou 49 pacotes. StartCommand da API em modo production com PostgreSQL/Redis locais: live/ready 200, admin anônimo 401, docs/OpenAPI 404; processo encerrado. JSONs parseados, `git diff --check` verde, gitleaks histórico sem vazamento.

**Falhas/limites registrados:** sandbox bloqueou registry/sockets e primeiras execuções; repetidas com permissão apropriada, cache de build bloqueado removido somente na cópia temporária. Primeira rodada E2E: aviso de hidratação no cenário site/contato, sem reprodução no cenário isolado ou rodada final; outra rodada: API 503 durante interferência do ambiente virtual de produção, resolvida separando/restaurando os ambientes de validação. Não houve mudança de produto nem diagnóstico comprovado da intermitência de hidratação. Build Railpack, auth/Google/WhatsApp reais e smoke de produção continuam não validados.

**Bloqueado por acesso:** `gh auth status` falhou dentro e fora do sandbox; conector GitHub autenticado para leitura, sem ferramenta de criação de repo; navegador recusou acesso ao GitHub pela política de permissão (não contornado). Railway retornou `USER_NOT_LOGGED_IN`. Supabase não tem Lumini; usuário autorizou criar, mas escolha da organização `relatorio de passagens`/custo segue pendente pelo contrato do conector. Variáveis reais de API/Google/Supabase/Redis/agenda não disponíveis; nomes e serviços em `DEPLOY.md`. Não houve push, compra, migração em produção ou deploy parcial apresentado como entrega.

**Processos:** preview Next existente PID 142577/3000, PostgreSQL PID 13488/55432, Redis PID 14385/56379 e Claude VS Code PID 6805 preservados; processos E2E/API iniciados pelos checks encerrados. Próximo passo executável no início de `HANDOFF.md`.

## 2026-10-14 — T12a retomada, GitHub e validação independente (Codex)

Baseline `main` limpa em `7fddf38`, 23 commits; os processos/portas Lumini antigos do handoff não existiam mais. A autenticação GitHub CLI agora está válida. Criado repositório público exclusivo `https://github.com/cdzaorib/lumini`, vazio inicialmente, remote `origin` HTTPS, push integral de `main` sem reescrever histórico. Primeiro CI remoto **verde**, run `38570501448`, SHA `7fddf386dfe43744b347894954eb3921d8827bb6`.

Validação independente do baseline: Ruff/format/mypy; **299 unitários e 189 integrações** PostgreSQL 15.19/Redis 7.0.15 sintéticos; Alembic upgrade/check sem drift; frontend lint/typecheck/build Node 22.23.2; gitleaks 23 commits sem vazamento. E2E em cópia isolada `/tmp/lumini-validation-20261014/checkout`: **7/7 cenários, 111/111 etapas**, console/CSP verdes. Instalação `uv sync --frozen --no-dev` isolada e smoke production local: live/ready 200, admin anônimo 401, docs/OpenAPI 404. Serviços temporários encerrados; nenhum fornecedor real validado.

Auditoria contra o plano integral corrigiu a premissa de que todo o código estava concluído: analytics/consentimento, mídia autorizada desacoplada, configuração revisada de mensagens, Jev específico, avaliação do redator/fallback e histórico persistente de encaminhamentos têm trabalho adicional. Execução em tarefas separadas, com posse de arquivos sem edições concorrentes; coordenador mantém os documentos.

Railway continua `USER_NOT_LOGGED_IN`; plugin instalado mas desconectado. Navegador não disponível (inventário vazio; Chrome e navegador integrado indisponíveis). Supabase conectado, organização `relatorio de passagens` plano Free, sem projeto Lumini; organização/custo precisam da escolha e confirmação exigidas pelo conector. Não há variáveis de credenciais Lumini no processo. Nenhuma compra, credencial em arquivo ou migração de produção.

## 2026-10-14 — T12b primeiro frontend remoto protegido (Codex)

Vercel existente `lumini`/equipe `cdzaoribs-projects`, build do GitHub `main` em `7fddf38`: deployment `dpl_96K3auJ3SLdsityGciX7J96FL1YE` **READY**, target retornado pela plataforma `production`, origem `https://lumini-cdzaoribs-projects.vercel.app` (alias adicional `lumini-taupe.vercel.app`). Nenhum projeto duplicado criado. Proteção SSO mantida; acesso anônimo redireciona para autenticação. Indexação fechada (`robots.txt` e noindex). Fetch autenticado pelo conector validou hero, `/admin` sem configuração, `/reserva`, `/privacidade` e robots, sem expor links temporários de acesso. API/worker/banco/Google/WhatsApp continuam ausentes; **este deploy é parcial e não constitui lançamento da clínica**. Não confirmar associação Git automática sem evidência.

## 2026-10-14 — T13a consentimento de analytics (Codex/agente)

Arquivos `frontend/src/app/_site/analytics-consent.tsx`, `frontend/src/lib/public/analytics.ts`, `frontend/checks/analytics-consent.mjs`, `chrome.tsx`, `privacidade/page.tsx`, `proxy.ts`. Controle acessível no rodapé para aceitar/recusar/revogar, sincronizado entre abas e com falha conservadora do armazenamento. Plausible só mede pageview de `/` com domínio configurado e consentimento: URL canônica limpa, sem cookie/Referer/propriedades/identificadores acrescentados pela aplicação ou conteúdo de contato/chat/reserva. CSP permite somente endpoint oficial configurado na landing; nenhuma medição nas rotas sensíveis.

ESLint/TypeScript/diff verdes; check de navegador interceptando fornecedor confirmou ausência de chamadas antes do consentimento, recusa/revogação/reload/abas/quota, payload mínimo, rotas sensíveis, CSP e largura 390px. Processo temporário3117 encerrado. Build integral será feito na integração final. `NEXT_PUBLIC_PLAUSIBLE_DOMAIN` só será preenchida quando houver conta/domínio aprovados; sem conta/compra/chamada real. Meta Pixel tem apenas parser de configuração preparado, **sem runtime implementado e sem tag carregada**; permanece pendente até campanha, contrato oficial verificado e consentimento separado. Isso não é apresentado como Pixel funcionando.

## 2026-10-14 — T13b Jev específico e avaliação comparativa (Codex/agente)

Contrato oficial Jev verificado (`https://api.typesafe.ai/openapi.json`, API0.2.0): `/v1/systemone` com Bearer, estado/perguntas choice, respostas tipadas e tokens; `/v1/models` sem chave recusa403. Adaptador independente em `ai/jev.py`, `SplitAssistant` com redator compatível DeepSeek, campos explícitos Settings (`LUMINI_AI_CLASSIFIER_PROVIDER`, `LUMINI_JEV_API_KEY`, `LUMINI_JEV_MODEL`). Nenhum nome de modelo inventado. IA continua desligada; conta/chave/modelo e bancada real permanecem pendentes. Confiança usa campo retornado, menor valor intenção/serviço por prudência; limiares não calibrados.

`ai/evaluation.py` cobre classificador+redator, fatos/refusas/privacidade, faixas de confiança, tentativas/tokens/latência/custo por modelo e comparação de relatórios numéricos. Custos incompletos explicitados quando falta uso/preço; nenhum texto/pergunta/resposta nos relatórios. Fallback disponível somente como candidato explícito, nunca montado automaticamente por `build_assistant`. Corrigido log de finish_reason arbitrário do fornecedor para código fixo. Arquivos: `ai/assistant.py`, `benchmark.py`, `client.py`, `jev.py`, `evaluation.py`, `tests/test_jev.py`, `tests/test_ai_evaluation.py`, Settings/testes. **71 testes IA**, Ruff/mypy 11 arquivos, CLI help e diff verdes; só mocks, nenhuma chamada autenticada real.

## 2026-10-14 — T13c conteúdo revisado, fotos e textos operacionais (Codex/agente)

Migração 0009 converte qualquer conteúdo anterior em rascunho. Site PUT salva rascunho, aprovações individuais pela identidade backend atribuída e publicação explícita só com todas as profissionais verificadas. Edição/retirada e operações reais update/verify/revoke de credenciais invalidam aprovações/publicação; reverificar não republica sozinho. Fotos com autorização, alt/dimensões e origem HTTPS explícita em API+Next, sem query/segredo; galeria otimizada, redirects0, nenhum storage/foto real inventado.12 textos operacionais editáveis sob a mesma revisão; placeholders limitados/substituição literal, saúde/STOP/reserva em processamento/sinal/regras/aftercare preservados. Pix e overrides só publicados.

Revisão independente encontrou e corrigiu: revogação de revisora não publicadora, revalidação que restaurava publicação, override que podia afirmar confirmação prematura, reenvio de body retirado e redirects de imagens fora da origem. Mutação de conteúdo/credenciais descarta replies pendentes e incrementa versões sem alterar modo humano; snapshot antigo e dedupe retirado não são reenviados. Catálogo/Site no-store no frontend. Testes pela API real de ambas as profissionais e de queda→edição/retirada→retry; revisora confirmou fixes sem regressão material. Mypy 105, Ruff,58 unitários Site/WhatsApp e88 integrações da unidade passaram. E2E07 final19/19, sem console/CSP.

Arquivos: Site/router/service, models/migração 0009, catalog/service, WhatsApp texts/flow/notifier e conversations helper/bot/webchat, testes Site/WhatsApp/settings, painel Site/fotos/textos/tipos/decoder, public loaders, next.config/media/page, e2e/server/cenário07. Nenhum fornecedor real nem autorização clínica substituída por teste.

## 2026-10-14 — T13d histórico mínimo e validação integrada (Codex)

Migração 0010 e `whatsapp/history.py` armazenam etapa+UUIDs e eventos de modo/encaminhamento, sem nome/telefone/mensagens clínicas. Guardam o estado antes de encaminhar; ordenação instante+versão preserva comandos no mesmo lote. Métricas contam eventos WhatsApp desde 0010, incluindo novos após #bot; não inventam passado/conversas distintas. Histórico web expira com sessão de 1 dia e não entra em métrica de longo período. Rota administrativa autenticada/no-store; testes de minimização, todos passos reais, persistência após #bot, deduplicação de modo e reply retirada.

Conjunto final: **368 unitários e 202 integrações**, `-W error`; Ruff 107 arquivos, mypy 105; migração 0010 e Alembic check sem drift; ESLint/TypeScript/build Next16.3.8 verdes. E2E completo final **7/7 cenários,118/118 etapas** em `/tmp/lumini-final-20261014-imrh92bc`, console/CSP verdes. Primeira tentativa da cópia falhou pela restrição Turbopack de node_modules symlink externo; dependências instaladas dentro da cópia, repetição passou sem alteração de produto. Environments backend distintos, sem reutilizar venv production no checkout.

`npm audit --omit=dev` zero avisos. Auditoria completa tem cinco entradas altas na cadeia dev/lint braces3.0.3, sem patch publicado em registry/advisory (GHSA-vfj7-8cjw-p6xm); downgrade incompatível sugerido pelo npm não aplicado. ESLint9 EOL já conhecido. Não apresentar auditoria completa como verde; manutenção em PENDENCIAS. Ferramentas/testes locais não validam Google, Evolution, IA, Supabase ou Railway reais.

Check final de consentimento (fornecedor interceptado) e allowlist de mídia passaram; instalação production isolada, 49 pacotes e smoke atual: live/ready 200, admin anônimo 401, docs/OpenAPI 404. Nenhum segredo em arquivo. Processos Next/API/PostgreSQL/Redis iniciados na validação encerrados; portas conferidas livres. Capturas em `/tmp/lumini-final-20261014-imrh92bc/e2e/.output/`.

Commits de código: `0532dc2`, `48ed326`, `342b77b`, enviados sem force. Gitleaks staged/histórico de 26 commits verde. CI remoto do código 342b77b verde, run 38577525488 (secrets/backend/frontend). Vercel final `dpl_aJvWeqHA7TLrNEiwBoJyY8jyRWY6` **READY**, mesmo projeto/equipe, target production e fonte 342b77b; SSO/noindex preservados, origem real configurada em Production. Fetch autenticado confirmou home/controle de privacidade, admin não configurado, reserva/robots. Não é aplicação completa: APIs/fornecedores reais continuam ausentes.

## 2026-10-14 — T14 lançamento: tarefas externas pendentes

Registro final em `PENDENCIAS.md`, com conexão Railway, organização/custo Supabase, navegador para dashboards, Google/Evolution/insumos clínicos, políticas/retenção/backups/piloto/IA e Git Vercel/domínio. Fontes públicas antigas consultadas read-only não fornecem credencial/aprovação clínica. Nenhuma infraestrutura de outro produto, compra, conta de provedor, migração remota, sinal automático, publicação de conteúdo não revisado ou substituição do Base44. Handoff atualizado com processos encerrados e próximo passo executável; produto permanece protegido e parcialmente publicado até satisfazer esses itens.

## 2026-10-14 — T14b auditoria de fidelidade e revalidação de bloqueios

Objetivo integral conferido contra PLANO-ORIGINAL/LANCAMENTO e estado atual: main e8b841a limpa, Railway novamente `USER_NOT_LOGGED_IN`, Supabase sem Lumini, navegador sem superfícies. Revisão independente identificou redução documental indevida ao dizer IA “se habilitada” e analytics “opcional”: corrigidos PENDENCIAS/DEPLOY/HANDOFF, com critérios reais por requisito em LANCAMENTO. Jev/DeepSeek/fallback e analytics continuam entregas exigidas; desligamento é gate provisório. Organização Supabase solicitada ao usuário conforme contrato do conector, sem resposta presumida e sem consulta/criação/custo aceito automaticamente. Nenhum teste repetido ou alteração de código; nenhuma integração remota pode ser marcada concluída.
