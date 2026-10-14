# Contrato da API administrativa — autenticação, catálogo (T07) e reservas (T08b)

Contrato de implementação em 2026-10-01, dentro do plano aprovado. Não implica Google real configurado.

**Estado (2026-10-01, Claude):** backend **implementado e testado localmente** (`lumini/auth.py`, `lumini/catalog/{schemas,service,router}.py`, migração `0002`). Painel em `/admin` **implementado (T07b)** e validado de ponta a ponta no Chrome contra a API e o PostgreSQL locais, com o script do Google substituído por stub e a identidade injetada no backend de teste (ver `VALIDACAO-002.md`). Login Google real **não validado**: falta Client ID de teste da clínica; o script real do Google carrega sob a CSP sem violações. API base é FastAPI; frontend fornece Google ID token apenas em `Authorization: Bearer ...`, mantido em memória, nunca em storage/cookies/URL/logs. Sem sessão baseada em cookies nesta etapa. Token com assinatura/audience/issuer/expiração/e-mail verificado e allowlist é exigido em **todas** as rotas `/api/admin/*`.

## Configuração e identidade

- Backend: `LUMINI_GOOGLE_CLIENT_ID`, `LUMINI_ADMIN_EMAILS` (JSON list), `LUMINI_REVIEWER_ASSIGNMENTS` (JSON mapping e-mail → list de UUIDs de profissionais). Sem configuração, acesso falha fechado.
- Frontend: `NEXT_PUBLIC_GOOGLE_CLIENT_ID` (identificador público) e `NEXT_PUBLIC_API_BASE_URL` (origem HTTP localhost em desenvolvimento, HTTPS em produção). Nenhum segredo no frontend.
- Contas aceitas: `@gmail.com` ou Google Workspace (claim `hd`, confiável porque a assinatura é verificada). Conta Google criada com e-mail de outro provedor (ex.: Yahoo/Hotmail) é recusada com 401, pois o Google não garante posse atual desse endereço. **Os e-mails da clínica precisam atender a isso.**
- Tolerância de relógio de 10s apenas para `iat`/`nbf`; `exp` estrito. Certificados do Google em cache só pelo `max-age` informado (teto 1h), sem redirect/retry e com limite de tamanho; o token do usuário nunca é enviado ao Google.
- Configuração é lida a cada requisição (sem sessão/cache de autorização); alterar a allowlist no ambiente exige reiniciar o processo.
- CORS (somente origens de `LUMINI_CORS_ORIGINS`): GET/POST/PATCH, cabeçalhos `Authorization`/`Content-Type`, sem credenciais/cookies.
- `GET /api/admin/me` → `{subject, email, reviewer_professional_ids: string[]}`. Identidade estável é o Google `sub`, não o e-mail. Allowlist usa o e-mail verificado. Revogação da allowlist vale a cada requisição.
- Erros JSON: `{detail: string}` ou validação FastAPI sanitizada; interface nunca apresenta mensagens brutas do provedor. 401=login inválido/expirado;403=sem permissão;409=conflito/estado incompleto;422=entrada inválida;503=dependência/configuração indisponível.

## Profissionais

- `GET /api/admin/professionals` → list `ProfessionalView`.
- `POST /api/admin/professionals` com `{display_name, category?, council_registration?}` → 201 view.
- `PATCH /api/admin/professionals/{id}` com `{expected_revision, display_name?, category?, council_registration?}` → view. Alterar credenciais/nome revoga verificação e aprovações de serviços associados.
- `POST /api/admin/professionals/{id}/verify` com `{expected_revision}` → view. Ato humano explícito após conferência documental; exige categoria/registro/nome preenchidos. Não é consulta automática ao conselho.
- `POST /api/admin/professionals/{id}/revoke` com `{expected_revision}` → view e invalida serviços vinculados.
- View: `{id, display_name, category, council_registration, credentials_verified_at, revision}`.

## Procedimentos

- `GET /api/admin/services` → list `ServiceView`.
- `POST /api/admin/services` →201; criação sempre draft, sem metadados de aprovação aceitos do cliente.
- `PATCH /api/admin/services/{id}` exige `expected_revision`; qualquer edição real revoga aprovações/publicação.
- `POST /api/admin/services/{id}/approve` com `{expected_revision, professional_id}`. Identidade deve estar atribuída àquele profissional na configuração. Todas as profissionais vinculadas precisam aprovar a revisão atual para status `approved`.
- `POST /api/admin/services/{id}/publish` com `{expected_revision}`. Exige todas as aprovações atuais, credenciais verificadas e conteúdo completo.
- `POST /api/admin/services/{id}/unpublish` com `{expected_revision}` volta a draft, revoga aprovações (conservador).
- `GET /api/catalog/services` → somente serviços atualmente publicados/elegíveis; nunca e-mails, sub, conselho interno ou trilha de auditoria. Revalida aprovações, credenciais e completude a cada leitura (`Cache-Control: no-store`). Profissionais públicas: `{id, display_name, category, council_registration}`, somente verificadas — publicidade de enfermagem exige identificação profissional (Cofen 554/2017) e o plano prevê credenciais na landing. Quem verificou, quando e as aprovações nunca são públicos. O `content` público omite `communication_restrictions`.

Comportamentos fixados na implementação: repetir verify/approve/publish devolve o estado atual (idempotente); unpublish em rascunho não altera nada; PATCH sem mudança real mantém revisão e publicação; editar/revogar profissional volta a rascunho **todos** os serviços vinculados e remove todas as aprovações deles; aprovação também exige sinal ≤ preço quando há preço. Erros 422 retornam `{detail: [{loc, type, msg}]}` sem o valor enviado.

Campos de criação/edição: `slug` (≤160), `name` (≤160), `category` (≤120, igual à coluna), `description: string|null`, `content`, `duration_minutes: number|null`, `buffer_minutes` (padrão15, mínimo15), `booking_mode: evaluation|direct|null`, `price_brl: string|null`, `deposit_brl: string|null`, `professional_ids: UUID[]`.

`content`: `{objectives: string[], audience: string|null, preparation: string[], aftercare: string[], human_guidance: string|null, price_kind: fixed|from|on_evaluation, communication_restrictions: string[]}`. `communication_restrictions` é a coluna “Restrições de comunicação” da matriz do plano: uso interno (guardrails do bot e revisão de divulgação), opcional, versionada e aprovada junto com o conteúdo. Campos clínicos são texto simples (sem HTML). Rascunho pode estar incompleto; aprovação exige description/objectives/audience/preparation/aftercare/human_guidance, duração/modo, pelo menos uma profissional verificada e sinal definido (zero é permitido). Preço obrigatório para fixed/from; em on_evaluation deve ser null.

`ServiceView`: todos os campos acima mais `id`, `status: draft|approved|published`, `revision`, `approved_at`, `published_at`, `approvals: [{professional_id, approved_at}]`. Aprovações são da revisão atual; dados de autoria permanecem apenas no registro interno. Uma ação de aprovação/publicação incrementa `revision`? **Não:** revision versiona conteúdo, não workflow. `expected_revision` protege contra edição de conteúdo desatualizada; transições de status são verificadas no banco.

## Consistência, autoria e testes

Mutação do catálogo em transação PostgreSQL com advisory lock dedicado ao catálogo (baixo volume), seguido de checagem de revisão/status. Isso serializa alteração de credencial e publicação, evitando corrida; não se aplica à agenda futura. Uma tabela de aprovações por profissional/revisão e auditoria de eventos mínimos (ator subject, alvo UUID, ação, revisão e horário) registra autoria sem copiar texto clínico.

Não aceitar status, aprovador, datas verificadas ou revisão arbitrária em DTOs de edição. Não habilitar bypass de login em configuração de runtime; fakes somente via injeção de dependência nos testes. Validação de entrada e erros não devem devolver a entrada original, tokens ou texto clínico. Sem acesso real ao Google, provas são criptográficas offline com chaves sintéticas e integração local PostgreSQL.

## Agenda e reservas da equipe (T08b)

**Estado (2026-10-05, Claude):** implementado e testado localmente (`lumini/booking/{router,queries,schedule,schemas}.py`, `lumini/deps.py`); painel com abas Reservas/Agenda/Catálogo validado no Chrome contra API e PostgreSQL locais com identidade e **calendário sintéticos** (`VALIDACAO-003.md`). Sem `LUMINI_GOOGLE_CALENDAR_CREDENTIALS` (chave JSON da conta de serviço, T08c/ADR-015), rotas que consultam o calendário respondem 503 `calendar_not_configured`. Com ela, o adaptador real é usado; ainda não validado contra o Google. Todas as rotas exigem o mesmo login/allowlist; autenticação ocorre antes de abrir sessão de banco ou tocar no calendário. Respostas com `Cache-Control: no-store`. CORS passou a incluir `PUT`.

Recusas: `{detail: string, code: string}`; ver ADR-014 para a lista de códigos. 404 `not_found`; 422 validação (sem eco da entrada); 409 estado/versão/regra; 503 `calendar_unavailable`/`calendar_not_configured` ou banco indisponível.

### Agenda da profissional

- `GET /api/admin/professionals/{id}/schedule` → `{professional_id, calendar_id: string|null, revision, rules: [{weekday, start, end}]}`. `revision` 0 = nunca configurada. `weekday` 0 = segunda; horas locais `America/Sao_Paulo` (`HH:MM:SS`).
- `PUT /api/admin/professionals/{id}/schedule` com `{expected_revision, calendar_id?: string|null, rules?: [{weekday, start: "HH:MM", end: "HH:MM"}]}` substitui calendário e faixas. Faixas em múltiplos de 15 min, início < fim, sem sobreposição no dia, ≤ 28; `calendar_id` em formato de e-mail (ID do Google Agenda). Revisão desatualizada → 409 `stale`; trocar `calendar_id` com reservas ativas ou remoções pendentes → 409 `calendar_in_use`. Não altera credenciais/aprovações; auditoria `schedule.updated` só com IDs.
- `GET /api/admin/availability?service_id&professional_id&first_day=YYYY-MM-DD&days=1..14` (padrão 7) → `{slots: [instante UTC]}`: mesma regra usada na reserva (faixas − reservas ativas − eventos de terceiros no Google, antecedência mínima 3h, horizonte 60 dias, grade 15 min). Procedimento de avaliação → 409 `evaluation_required`; agenda incompleta → 409 `agenda_not_configured`.

### Reservas

- `GET /api/admin/bookings?scope=upcoming|history` (padrão `upcoming`). `upcoming`: `pending_calendar`, `held`, `confirming`, `conflict` em qualquer data + `confirmed` que ainda não terminou, por início (até 500). `history`: demais (expiradas, canceladas, confirmadas já realizadas), mais recentes primeiro (até 100).
- `GET /api/admin/bookings/{id}` → view.
- View: `{id, code (8 hex), status, version, starts_at, ends_at, expires_at, service: {id, name}, professional: {id, name}, contact: {name, phone}, deposit_brl, deposit_confirmed_at, calendar_status, reschedule_count, rescheduled_from_id, closed_reason, created_at}`. **Nome e telefone só existem nesta API autenticada**; nunca em calendário, auditoria, outbox ou logs.
- `POST /api/admin/bookings/{id}/deposit` com `{expected_version, amount_brl}`: ato humano autenticado; valor precisa ser igual ao sinal previsto (`deposit_mismatch`), reserva em `held` e dentro do prazo (`hold_expired`). Vai a `confirming`; o worker confirma no Google e então `confirmed`.
- `POST /api/admin/bookings/{id}/cancel` com `{expected_version}`: equipe cancela qualquer reserva ativa a qualquer momento; evento é removido pelo outbox.
- `POST /api/admin/bookings/{id}/resolve` com `{expected_version, resolution: "release"|"retry"}`: só em `conflict`. `retry` volta a `pending_calendar` e a agenda é conferida de novo.
- `POST /api/admin/bookings/{id}/reschedule` com `{expected_version, starts_at (com fuso)}`: só `confirmed`; responde a **nova** reserva (`rescheduled_from_id` = original, sinal mantido); a original fica `cancelled`/`rescheduled`. Repetir a mesma chamada devolve a mesma reserva nova. Horário a menos de 3h → 409 `too_close`.

Toda ação de tela envia a versão vista; versão diferente → 409 `stale` sem efeito parcial.

### Link de autoatendimento da cliente (T08d)

- `POST /api/admin/bookings/{id}/manage-link` → `{url, expires_at}` para reservas `held`/`confirmed` futuras; auditado (`manage_link_issued`). Sem `LUMINI_MANAGE_LINK_SECRET` + `LUMINI_PUBLIC_SITE_URL` → 503 `manage_link_not_configured`. URL: `{site}/reserva#<token>`.

## API pública da cliente (T08d, sem login)

Credencial = token do link (HMAC-SHA256 sobre reserva + validade até o início do atendimento; ADR-016), enviado em `Authorization: Bearer <token>`, nunca na URL da API. Link adulterado, expirado, de outra chave ou de reserva inexistente → 404 `link_invalid` idêntico, antes de abrir sessão de banco. Sem segredo configurado → 503 `self_service_unavailable`. Limite por link: 120 requisições e 30 consultas de horários a cada 10 min (429 `rate_limited`). `Cache-Control: no-store`.

- `GET /api/public/booking` → `{code, status, version, service, professional, starts_at, ends_at, hold_expires_at, deposit_brl, deposit_confirmed, self_service_until, can_cancel, cancel_blocked, can_reschedule, reschedule_blocked}`. **Sem nome, telefone ou ids internos.** Motivos: `within_24h`, `second_reschedule`, `not_confirmed`, `in_progress`, `closed`.
- `GET /api/public/booking/availability?first_day&days=1..7` → `{slots}` só quando `can_reschedule`; o próprio horário não aparece.
- `POST /api/public/booking/cancel` com `{expected_version}`: reserva aguardando sinal a qualquer momento; confirmada só com mais de 24 h (no limite exato, humano). Devolução do sinal é decisão da clínica.
- `POST /api/public/booking/reschedule` com `{expected_version, starts_at}`: só confirmada, mais de 24 h e nenhum reagendamento anterior; sinal mantido. Resposta `{booking, token}` com o link da **nova** reserva; o link antigo passa a mostrar a original cancelada.

## WhatsApp (T09)

- `POST /api/webhooks/evolution` (Evolution → API). Exige `Authorization: Bearer <LUMINI_EVOLUTION_WEBHOOK_TOKEN>` (401), instância igual a `LUMINI_EVOLUTION_INSTANCE` (403), corpo ≤ 1 MB (413), JSON objeto (400); sem configuração → 404. Eventos tratados: `messages.upsert`/`send.message` (mensagens), `connection.update`, `qrcode.updated`; demais ignorados com 200. Banco indisponível → 503. Detalhes em ADR-017 e `RUNBOOK-WHATSAPP.md`.
- `GET /api/admin/integrations` → `{whatsapp: {configured, state, needs_attention, changed_at, human_mode_conversations}, calendar_configured, self_service_configured}`. Estados: `open`, `connecting`, `close`, `qr_required`, `unknown`; configurado sem notícia da instância conta como `needs_attention`.

## Pedidos de contato / leads (T10b)

- `POST /api/public/leads` (site, sem login) com `{name, phone, city?, service_id?, preferred_period: morning|afternoon|any, contact_consent: true, marketing_consent?, website: ""}` → 201 `{ok: true}` (mesma resposta para gravado, atualizado ou armadilha de robô). Telefone brasileiro com DDD ou E.164. **Não há campo de texto livre** (poderia trazer dado de saúde). Procedimento não publicado é descartado. Reenvio do mesmo telefone em 24 h atualiza o pedido. Limite de 5 envios por endereço a cada 10 min (429). 422 sem eco.
- `GET /api/admin/leads?status=new|contacted|converted|discarded` (padrão `new`, até 200) e `POST /api/admin/leads/{id}/status` com `{status}` → 204.
- Retenção: não convertidos são apagados na data `retain_until` (90 dias, plano §12) pelo tick do worker; convertidos seguem a política de agendamentos (a aprovar antes do lançamento).

## Chat do site (T10d)

- `POST /api/public/chat/session` → 201 `{token, replies, options}`. Token aleatório (43 caracteres) guardado só pelo navegador; o servidor guarda o hash. Limite de 20 sessões por endereço a cada 10 min.
- `POST /api/public/chat/messages` com `Authorization: Bearer <token>` e `{text}` (≤ 1000) → `{replies, options}`; `options` são as opções numeradas da última resposta. Erros com `{detail: {code}}`: 404 `session_invalid` (token malformado, desconhecido ou com mais de 24 h; recusado antes do banco), 409 `stale` (duas mensagens ao mesmo tempo; reenviar), 429 `rate_limited` (60 por sessão a cada 10 min), 503 `chat_unavailable`. Nenhum texto é gravado.

## Conteúdo do site (T11a, revisão obrigatória T13c)

- `GET /api/admin/site` → revisão/conteúdo/data, `status` draft/approved/published, publicação, revisoras obrigatórias/elegíveis e respectivas aprovações, origens de mídia e opções de texto operacional. Revisão0 = nunca preenchido. `PUT /api/admin/site` com `{expected_revision, content}` salva **rascunho** e revoga aprovações/publicação; 409 se desatualizado, 422 sem eco em campo/publicidade/placeholder inválido. Campos anteriores mantidos; novos `photos[{url, alt, width, height, authorized_on, authorization_confirmed: true}]` e `bot_texts {chave: template}`.
- `POST /api/admin/site/approve` e `/site/publish`: `{expected_revision, professional_id, review_confirmed: true}`. Aprovação exige atribuição backend à profissional verificada; publicação exige todas as profissionais verificadas aprovarem a revisão global e uma revisora autorizada executar a publicação. 403 sem atribuição; 409 se revisão/credencial/aprovação/origem de imagem inválida. `POST /api/admin/site/unpublish` com `{expected_revision}` retira publicação/aprovações. Alterar/revogar/reverificar credenciais invalida a revisão; não restaura conteúdo automaticamente.
- `GET /api/public/site` (sem login, `no-store`) retorna somente conteúdo publicado e ainda revisado; sem publicação, conteúdo vazio. Não expõe instruções Pix, textos do bot nem registros de autorização. O frontend também não guarda cache de Site ou catálogo revogado.
- Fotos só de origens HTTPS explícitas `LUMINI_MEDIA_ORIGINS`, sem usuário/senha/query/fragmento; autorização humana registrada, alt e dimensões. Galeria e otimizador Next usam a mesma allowlist e não seguem redirects. Nenhum storage/foto real é criado automaticamente.
- Textos operacionais têm chaves/placeholders fechados e substituição literal single-pass. Saúde, STOP, reserva/sinal/limites/links e recomendações clínicas permanecem no código/catálogo aprovado. Instruções Pix e overrides só usados após publicação. Mudança/retirada do conteúdo ou credenciais descarta replies pendentes e incrementa versões das conversas, sem mudar modo humano; o próximo texto usa o conteúdo atual.

## Comparecimento, histórico e métricas (T11b)

- `POST /api/admin/bookings/{id}/attendance` com `{expected_version, attendance: attended|no_show}`: só reservas confirmadas e depois do início (`too_early`); depois disso a reserva não aceita cancelamento nem reagendamento (`attendance_recorded`). Faltas não recebem a mensagem de recomendações pós-procedimento.
- `GET /api/admin/bookings/{id}/events` → `[{action, from_status, to_status, actor: system|staff|client, at}]` (sem identificar a pessoa da equipe).
- `GET /api/admin/metrics?days=1..365` → contagens do período (pedidos de contato por situação e com consentimento de marketing, reservas pedidas e por origem, sinais confirmados, atendimentos/comparecimentos/faltas/sem marcação, cancelamentos por motivo, reagendamentos, expirações por motivo, procura por procedimento, **eventos de encaminhamento WhatsApp** por motivo, confirmados nos próximos 7 dias). Encaminhamentos são eventos desde migração 0010, inclusive novo encaminhamento após #bot; não representam conversas distintas nem histórico retroativo inventado. `BookingAdminView` mantém `attendance` e `origin`.
- `GET /api/admin/conversations/{conversation_id}/history` → até 100 eventos recentes `{kind, reason, version, summary, occurred_at}`, com autenticação e no-store. Resumo guarda apenas etapa e UUIDs de serviço/profissional, nunca nome/telefone/mensagem clínica. Ordenação por instante e versão preserva ordem de comandos no mesmo webhook. Histórico web acompanha retenção da sessão1 dia; histórico WhatsApp segue a política separada de retenção a aprovar. A métrica de encaminhamentos é explicitamente WhatsApp, evitando totais web incompletos em janelas maiores.
