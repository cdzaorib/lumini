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

Mutações do catálogo ocorrem em uma transação com `pg_advisory_xact_lock` dedicado (baixo volume), seguida de checagem de `expected_revision`. `revision` versiona conteúdo, não workflow; aprovações são por profissional **e** revisão. Edição de serviço, alteração/revogação de profissional e despublicação voltam a rascunho e removem aprovações (conservador). A trava é exclusiva do catálogo: a agenda (T08) precisa de restrição transacional própria, não desta trava. Registro de conselho não é exposto no catálogo público até haver campo público revisado.
