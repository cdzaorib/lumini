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
| T11 | Itens restantes do plano só com código (conteúdo do site no painel, métricas, comparecimento, alerta de sobreposição, E2E versionado, revisões) | Em andamento | Pedido do usuário: “pode continuar até o final”; deploy continua exigindo autorização específica |

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
