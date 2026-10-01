# Contrato de T07 — autenticação e catálogo

Contrato de implementação em 2026-10-01, dentro do plano aprovado. Não implica Google real configurado.

**Estado (2026-10-01, Claude):** backend **implementado e testado localmente** (`lumini/auth.py`, `lumini/catalog/{schemas,service,router}.py`, migração `0002`). Painel frontend **não iniciado** — existe apenas a biblioteca `frontend/src/lib/admin` (cliente/decoders/sessão em memória), sem página nem Google Identity Services. Login Google real **não validado**: provas são criptográficas offline com chaves sintéticas. API base é FastAPI; frontend fornece Google ID token apenas em `Authorization: Bearer ...`, mantido em memória, nunca em storage/cookies/URL/logs. Sem sessão baseada em cookies nesta etapa. Token com assinatura/audience/issuer/expiração/e-mail verificado e allowlist é exigido em **todas** as rotas `/api/admin/*`.

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
- `GET /api/catalog/services` → somente serviços atualmente publicados/elegíveis; nunca e-mails, sub, conselho interno ou trilha de auditoria. Revalida aprovações, credenciais e completude a cada leitura (`Cache-Control: no-store`). Profissionais públicas: `{id, display_name, category}`; o registro de conselho fica interno até existir campo público de credencial revisado.

Comportamentos fixados na implementação: repetir verify/approve/publish devolve o estado atual (idempotente); unpublish em rascunho não altera nada; PATCH sem mudança real mantém revisão e publicação; editar/revogar profissional volta a rascunho **todos** os serviços vinculados e remove todas as aprovações deles; aprovação também exige sinal ≤ preço quando há preço. Erros 422 retornam `{detail: [{loc, type, msg}]}` sem o valor enviado.

Campos de criação/edição: `slug`, `name`, `category`, `description: string|null`, `content`, `duration_minutes: number|null`, `buffer_minutes` (padrão15, mínimo15), `booking_mode: evaluation|direct|null`, `price_brl: string|null`, `deposit_brl: string|null`, `professional_ids: UUID[]`.

`content`: `{objectives: string[], audience: string|null, preparation: string[], aftercare: string[], human_guidance: string|null, price_kind: fixed|from|on_evaluation}`. Campos clínicos são texto simples (sem HTML). Rascunho pode estar incompleto; aprovação exige description/objectives/audience/preparation/aftercare/human_guidance, duração/modo, pelo menos uma profissional verificada e sinal definido (zero é permitido). Preço obrigatório para fixed/from; em on_evaluation deve ser null.

`ServiceView`: todos os campos acima mais `id`, `status: draft|approved|published`, `revision`, `approved_at`, `published_at`, `approvals: [{professional_id, approved_at}]`. Aprovações são da revisão atual; dados de autoria permanecem apenas no registro interno. Uma ação de aprovação/publicação incrementa `revision`? **Não:** revision versiona conteúdo, não workflow. `expected_revision` protege contra edição de conteúdo desatualizada; transições de status são verificadas no banco.

## Consistência, autoria e testes

Mutação do catálogo em transação PostgreSQL com advisory lock dedicado ao catálogo (baixo volume), seguido de checagem de revisão/status. Isso serializa alteração de credencial e publicação, evitando corrida; não se aplica à agenda futura. Uma tabela de aprovações por profissional/revisão e auditoria de eventos mínimos (ator subject, alvo UUID, ação, revisão e horário) registra autoria sem copiar texto clínico.

Não aceitar status, aprovador, datas verificadas ou revisão arbitrária em DTOs de edição. Não habilitar bypass de login em configuração de runtime; fakes somente via injeção de dependência nos testes. Validação de entrada e erros não devem devolver a entrada original, tokens ou texto clínico. Sem acesso real ao Google, provas são criptográficas offline com chaves sintéticas e integração local PostgreSQL.
