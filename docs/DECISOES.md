# Decisões técnicas

## ADR-001 — Python no backend (aprovada pelo usuário)

FastAPI/Pydantic, SQLAlchemy/Alembic, Celery/Redis; Next.js permanece no frontend. PyCharm é IDE, não dependência de runtime. Não assumir que Python é universalmente superior: a escolha reflete preferência do usuário e adequação ao projeto. Ambos os ecossistemas atendem ao escopo.

## ADR-002 — Monorepositório, worker compartilhado

`frontend/`, `backend/`, `infrastructure/`, `docs/`. Worker dentro do pacote Python evita duplicação. API e worker serão processos separados na implantação. Nada é criado em Railway/Vercel nesta fundação local.

## ADR-003 — Agenda distribuída com reconciliação

Google Calendar fornece disponibilidade e eventos operacionais. PostgreSQL registra holds, confirmações e outbox. Futuro: restrição transacional de sobreposição por profissional, idempotency keys, jobs deduplicados, reconciliação e compensação. TTL Redis não é fonte única para expiração; armazenar `expires_at` no PostgreSQL. Sem transação atômica entre Google e banco: em estado incerto, não confirmar ao cliente.

## ADR-004 — Conteúdo e IA desacoplados

IA recebe somente contexto mínimo aprovado e anonimizado. APIs externas atrás de interfaces; implementação e benchmark de provedores virão depois. Não herdar as integrações/segredos do Tecnoarte ou SalvaMoney. A revisão humana do conteúdo não é substituída pelo modelo.

## ADR-005 — Fundação executável sem credenciais

Healthcheck de vida local não deve dizer que banco/Redis/fornecedores estão conectados. Readiness só dá sucesso após verificar suas dependências. Exemplos sem credenciais; testes sintéticos. Não expor endpoint administrativo/pagamentos antes da autorização backend. Desenvolvimento pode iniciar sem conectar serviços externos.

## ADR-006 — Limite de 24h e privacidade

Implementação inicial conservadora: autoatendimento somente com antecedência estritamente superior a 24h; no limite exato, humano. Confirmações tardias de sinal, valor divergente e conflitos precisam de revisão humana. Não pedir detalhes sobre condições; o sinal de encaminhamento basta.

## ADR-007 — Fronteira dos provedores e texto livre

Resposta afirmativa à pergunta sobre condição de saúde é tratada localmente e encaminhada sem passar por Jev/DeepSeek. Contratos de IA devem aceitar apenas contexto estruturado permitido, nunca mensagens brutas. Minimização de texto livre ainda não está demonstrada: exige avaliação específica antes de habilitar chamadas de modelo; na dúvida, responder com conteúdo fixo ou encaminhar. Não prometer anonimização perfeita por regex.

## ADR-008 — Concorrência e saída de mensagens (antes da Fase 2/3)

Reservas terão estados explícitos (`pending_calendar`, `held`, `confirming`, `confirmed`, `expired`, `conflict`), operação idempotente e identificador remoto. Confirmação de sinal e expiração devem competir pela mesma transição condicional, com bloqueio transacional e relógio persistido. Janela mínima para reserva será pelo menos 2h antes do atendimento; consulta de horários muito próximos deve encaminhar para humano. Esta é regra técnica conservadora a documentar na interface.

Modo humano persistido inclui versão da conversa; todo envio automático revalida versão/modo antes do despacho, inclusive texto já gerado/na fila. `fromMe` isolado não comprova mensagem humana. PoC deve distinguir mensagem manual, envio pela API e reentrega de webhook. STOP suspende mensagens opcionais; não cancela uma reserva nem reativa automação. Política transacional detalhada será definida antes do envio real.

## ADR-009 — Retenção e orçamento verificáveis

Lead, consentimentos, agendamentos e auditoria precisam de retenções separadas, sem cascata de exclusão indiscriminada. Filas/outbox carregam IDs e eventos mínimos. Custos incluem todas as tentativas e fallbacks; registrar tokens/latência/custo sem prompts. Meta de R$100–300 será aferida com uso e topologia reais; ainda não validada.

## ADR-010 — Autenticação administrativa por Google ID token (T07)

Painel envia o Google ID token como `Authorization: Bearer`, mantido só em memória; sem cookies/sessão no backend nesta etapa, logo CORS permite GET/POST/PATCH com `Authorization` apenas às origens configuradas e sem credenciais. Backend verifica assinatura/audience/issuer/expiração, `email_verified` e allowlist em toda rota `/api/admin/*`, antes de abrir sessão de banco. Identidade estável é o `sub`; allowlist usa o e-mail. Contas com e-mail externo ao Google (sem `@gmail.com` nem `hd` de Workspace) são recusadas por não haver garantia de posse atual do endereço. Sem bypass de login em runtime; testes injetam verificador/principal via dependência.

## ADR-011 — Fluxo do catálogo serializado e versionado (T07)

Mutações do catálogo ocorrem em uma transação com `pg_advisory_xact_lock` dedicado (baixo volume), seguida de checagem de `expected_revision`. `revision` versiona conteúdo, não workflow; aprovações são por profissional **e** revisão. Edição de serviço, alteração/revogação de profissional e despublicação voltam a rascunho e removem aprovações (conservador). A trava é exclusiva do catálogo: a agenda (T08) precisa de restrição transacional própria, não desta trava. Registro de conselho de profissionais **verificadas** é público (revisto em T07b: Cofen 554/2017 exige identificação profissional na publicidade de enfermagem e o plano prevê credenciais na landing); metadados de verificação e aprovação continuam internos.

## ADR-012 — Painel com CSP por nonce e token só em memória (T07b)

`/admin` é renderizado por requisição: `src/proxy.ts` gera nonce e CSP (`script-src 'nonce' 'strict-dynamic'`, `connect-src` limitado à API configurada e ao GIS, `frame-src` só GIS, `base-uri 'none'`, `frame-ancestors 'none'`, `no-store`); `'unsafe-eval'` apenas em desenvolvimento. A landing segue estática e sem CSP até a fase da landing definir a sua. O ID token do Google fica só em memória (`AdminSession`); sair, recarregar a aba ou expirar (401) exige novo login. Sem Client ID/API válidos o painel mostra “não configurado” e nem carrega o script do Google. Fluxos de teste usam identidade injetada no backend e stub do script do Google no navegador; não existe bypass de login no código da aplicação.

## ADR-013 — Núcleo de reservas (T08a)

- **Disponibilidade** = regras semanais por profissional no PostgreSQL (hora local `America/Sao_Paulo`, editadas no painel) ∩ livre no Google Calendar (eventos de terceiros) ∩ sem reserva ativa no PostgreSQL. Eventos da própria Lumini (`id` com prefixo `lumini`) são ignorados no Google porque o banco já os contabiliza.
- **Trava por profissional e horário**: restrição `EXCLUDE USING gist` (extensão `btree_gist`) sobre `[início, fim + intervalo)` para os estados `pending_calendar`, `held`, `confirming`, `confirmed` e `conflict`. Corrida de reservas é resolvida pelo banco, sem Redis (provado com conexões concorrentes).
- **Estados**: `pending_calendar` (até 10 min para criar o evento provisório) → `held` (2h contadas a partir do evento criado; só então a cliente recebe instruções) → `confirming` (sinal conferido por humano autenticado; expiração não vence mais) → `confirmed` (evento confirmado no Google). `expired`, `cancelled` e `conflict` (humano decide: liberar ou tentar de novo). Sinal e expiração disputam a mesma linha bloqueada; versão otimista em toda ação de tela.
- **Google Calendar**: id do evento derivado da reserva (`lumini` + uuid), logo criar/atualizar/excluir são idempotentes e resposta perdida é reconciliável. Nenhuma chamada externa dentro de transação do banco. Evento sem nome, telefone ou texto clínico (só procedimento, situação e código curto). Falha transitória → retry com backoff; recusa permanente ou evento de terceiro sobreposto → `conflict` e encaminhamento humano.
- **Regras fixas** (`BookingPolicy`): grade de 15 min; horizonte de 60 dias; antecedência mínima de **3h** (ADR-008 exige ao menos 2h; +1h para a confirmação humana caber antes do atendimento) — horários mais próximos vão para humano; autoatendimento de cancelamento/reagendamento só com **mais de** 24h; primeiro reagendamento pela cliente preserva o sinal, segundo é decisão humana; equipe pode cancelar/reagendar sempre, com auditoria.
- **Somente serviços `direct` são reserváveis online**; serviços “avaliação primeiro” exigem um serviço de avaliação próprio no catálogo.
- **Sinal zero também exige confirmação humana** (conservador: nada é confirmado automaticamente). Revisar com a clínica.
- **Outbox transacional** (entrega ao menos uma vez, chave de deduplicação): sincronização de calendário e mensagens (`hold_created`, `deposit_instructions`, `hold_expiring`, `hold_expired`, `booking_confirmed`, `booking_rescheduled`, `manage_link`, `reminder_24h`, `reminder_2h`, `aftercare`, `booking_cancelled`, `human_handoff`). Toda mensagem é revalidada contra o estado atual antes do envio; sem canal configurado ficam pendentes. Lembretes não são enviados se a confirmação ocorreu depois da hora do lembrete. Auditoria e outbox guardam só IDs.

## ADR-014 — API e painel de agenda/reservas da equipe (T08b)

- **Erros com código estável**: recusas de reserva respondem `{detail, code}` (`detail` em inglês fixo, `code` estável que o painel traduz: `stale`, `invalid_state`, `deposit_mismatch`, `hold_expired`, `too_close`, `slot_unavailable`, `calendar_in_use`, `evaluation_required`, `agenda_not_configured`, `not_bookable`, `not_found`, `calendar_unavailable`, `calendar_not_configured`). 404/403/422/409/503 conforme o tipo; texto de fornecedor ou driver nunca volta na resposta. O formato `{detail: string}` do catálogo continua válido.
- **Troca de calendário bloqueada com reservas dependentes**: `calendar_id` só muda quando a profissional não tem reserva ativa nem evento ainda não removido no Google (`calendar_status` `tentative`/`confirmed`). A sincronização escreve sempre no calendário atual; trocar no meio deixaria eventos órfãos no antigo. Mudar só as faixas é livre e não move reservas existentes.
- **Faixas da agenda em múltiplos de 15 min**, sem sobreposição no mesmo dia, até 28 por semana, hora local sem fuso. A grade de horários parte do início de cada faixa.
- **Agenda separada de credenciais**: `PUT /schedule` usa `expected_revision` próprio (0 = ainda não configurada) e registra `schedule.updated` na auditoria do catálogo; não revoga verificação nem aprovações.
- **Leituras sem trava relêem do banco** (`populate_existing`) em `sync_calendar`, idempotência, reagendamento e checagem de relevância das mensagens. Motivo: as sessões usam `expire_on_commit=False` e o worker pode reaproveitar uma sessão; com cópia antiga, um cancelamento feito pelo painel era tratado como "sem mudança" (evento ficava no Google) e a mensagem "reserva criada" seguia para uma reserva cancelada. Leituras com `FOR UPDATE` já relêem (verificado empiricamente).
- **Painel abre em Reservas** (operação diária); Agenda e Catálogo ficam em abas. Confirmação de sinal exige digitar o valor recebido e marcar a conferência do crédito na conta (comprovante da cliente não basta); a API recusa valor diferente do previsto.
