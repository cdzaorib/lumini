# Decisões técnicas

## ADR-020 — Consentimento e medição mínima na landing (2026-10-14)

O plano exige analytics somente após consentimento. Medição opcional de pageview usa Events API do Plausible, sem dependência ou script de autocaptura: apenas `/`, com URL canônica sem query/fragmento e sem Referer/cookies/propriedades enviados pela aplicação. O domínio é configuração da clínica, sem criação/assinatura automática de serviço. Recusar/revogar impede chamadas futuras, inclusive após reload ou em outras abas; erro de persistência não restaura consentimento antigo. Rotas de painel, atendimento, reservas e legais não emitem eventos. A transmissão de IP/headers inerentes à conexão com o fornecedor deverá constar da revisão jurídica antes da configuração real.

Meta Pixel continua sem execução; configuração validada é apenas preparação, não integração concluída. Campanha/consentimento de marketing e contrato oficial precisam ser verificados antes de implementar/habilitar o runtime. Referência técnica consultada: https://plausible.io/docs/events-api.

## ADR-021 — Jev estruturado e escolha de fallback por evidência (2026-10-14)

Jev não usa chat/completions: o contrato oficial System One foi verificado e tem cliente próprio, chave/modelo explícitos e respostas validadas, separado do redator DeepSeek. Serviços precisam estar no catálogo conhecido; falha/retorno inválido não abre acesso a regras, banco ou calendário. O classificador usa a confiança retornada, e o mínimo entre intenção/serviço quando ambos são necessários; isso não prova calibração. IA continua desligada até revisão da minimização e bancada real. Benchmark ampliado mede classificador+redator e compara candidatos sem guardar textos nem escolher fornecedor automaticamente. Fallback de modelo só pode ser escolhido após essa medição; o fallback determinístico aprovado continua vigente. Fonte: https://api.typesafe.ai/openapi.json.

## ADR-022 — Revisão global do site e retirada conservadora (2026-10-14)

FAQ e conteúdo do Site não têm área clínica por item: exige aprovação de todas as profissionais verificadas, cada uma autenticada e atribuída no backend, mais publicação explícita. Uma mudança de conteúdo ou de credencial invalida as aprovações; reverificação não repõe publicação. Salvar/retirar e invalidar catálogo descarta replies pendentes e incrementa versões de conversas sem mudar modo, impedindo resposta antiga já persistida ou ainda gerada de sair após retirada. Notificações são remontadas do estado/conteúdo atual; não há garantia distribuída de desfazer envio já em andamento. Regras de saúde/STOP/reserva/sinal/links/aftercare continuam determinísticas. Mídia por URLs autorizadas com origens explícitas, Next sem redirects e sem storage acoplado.

## ADR-023 — Histórico estruturado sem transcrição (2026-10-14)

Eventos de progresso/mudança de modo guardam apenas etapa conhecida e IDs de serviço/profissional; não resumo livre gerado por modelo, nomes/telefones ou texto clínico. Métricas de encaminhamento são eventos WhatsApp desde 0010; histórico de sessão web acompanha a retenção de 1 dia e não é usado para totais incompletos de períodos maiores. API de histórico continua administrativa/no-store, sem criar caixa de atendimento humano no painel. Retenção WhatsApp/agendamentos/financeiro depende da política da clínica antes do lançamento.

## ADR-019 — Hospedagem Vercel, Supabase PostgreSQL e Railway (2026-10-06)

O usuário autorizou preparar/publicar a Lumini e esclareceu que este checkout deve preservar FastAPI, Celery/Redis e o login Google. Supabase passa a ser o provedor do PostgreSQL; frontend na Vercel, API/worker/Redis no Railway. Isso substitui somente a escolha de provedor PostgreSQL dos planos anteriores; não migra a autorização para Supabase Auth nem reimplementa regras no Data API. Supabase Storage não é usado atualmente.

O frontend continua consumindo a API FastAPI. `LUMINI_DATABASE_URL` pertence apenas à API/worker e às migrações; nenhuma chave Supabase é necessária no navegador. Usar conexão direta ou pooler em modo sessão, compatível com conexões persistentes e prepared statements do asyncpg. O endpoint real deve vir do painel, com TLS, sem inventar host ou credencial. Antes de criar tabelas no novo projeto, desativar o Data API que não será usado e verificar a ausência de acesso por `anon`/`authenticated`; a autorização administrativa permanece no backend. Não aplicar migrações em projetos de outros produtos.

Arquivos separados de configuração Railway para API e worker: raiz `/backend`, paths `/backend/railway.api.json` e `/backend/railway.worker.json`; instalação com `uv.lock` congelado, um worker com beat e uma réplica. Migrações são uma operação explícita, fora do start/pre-deploy automático; somente após conferir projeto e estado do banco. Preview não deve usar banco/contas de produção. Detalhes, credenciais pendentes e evidências em `DEPLOY.md`.

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

## ADR-015 — Worker periódico, adaptador Google e reconciliação (T08c)

- **Adaptador Google sem SDK pesado**: REST v3 com `requests` (já dependência via `google-auth`) em threads, token da conta de serviço emitido localmente por `google-auth` (prazo de 10 s em vez dos 120 s padrão) e renovado sob trava. Escopo mínimo `calendar.events`. `list_busy` usa `events.list` (precisa dos ids para ignorar os eventos da Lumini; FreeBusy não devolve ids), ignora eventos “disponível”/cancelados e trata evento de dia inteiro como ocupando o dia em Brasília. Página ilegível, evento malformado ou mais de 10 páginas = indisponível, **nunca** “livre”.
- **Classificação de falhas**: rede, timeout, 429, 5xx, cota (403 `rateLimitExceeded`) e falha do token → `CalendarUnavailable` (reserva nova é recusada; job tenta de novo). Calendário inexistente ou não compartilhado (403/404) e 400 → `CalendarRejected` (vira conflito para a equipe). 401 tenta uma vez com token novo. Chave revogada fica como indisponível (não gera conflito em massa); aparece nos logs pelo código `token_refused`.
- **Upsert**: `PUT` primeiro (também restaura evento apagado, que o Google mantém como `cancelled`), `POST` se não existir, `PUT` de novo se outro processo criou no meio. `DELETE` com 404/410 = concluído.
- **Identificação estrita** dos eventos da Lumini: `lumini` + 32 hex exatos. Um evento manual cujo id apenas comece com `lumini` continua contando como ocupado.
- **Worker**: Celery beat embutido; tick a cada 60 s e reconciliação a cada 15 min, cada execução com engine/sessão novas e trava Redis não bloqueante (TTL 5 min). Sem credencial do Google, o tick só expira e agenda mensagens; jobs de calendário aguardam.
- **Reconciliação**: (1) reserva cujo estado no calendário nunca convergiu (ex.: `confirming` depois que o job desistiu) ganha novo job, no máximo um por hora; (2) a cada 15 min, os eventos da Lumini no horizonte de 60 dias são comparados com as reservas `held`/`confirmed` e encerradas: evento apagado ou movido no Google é recolocado; evento de reserva encerrada que reapareceu é removido de novo. O PostgreSQL decide; cada reparo é auditado (`calendar_drift`, sem mudar status/versão). Reservas em andamento e em conflito ficam com o job ou com a equipe.
- **Compromisso de terceiros sobre reserva ativa** (T11c, leitura conservadora): a reconciliação marca `calendar_overlap_at`, registra `calendar_overlap`/`calendar_overlap_cleared` no histórico e o painel mostra o aviso; a reserva **não** muda de estado nem é cancelada. Se a clínica preferir outra conduta (ex.: mensagem automática à cliente), é decisão de produto.

## ADR-016 — Autoatendimento por link assinado (T08d)

- **Token sem estado**: `uuid da reserva + validade + HMAC-SHA256` (domínio separado, comparação em tempo constante), validade até o início do atendimento. Nada guardado no banco; trocar `LUMINI_MANAGE_LINK_SECRET` revoga todos os links. Erros de link são indistinguíveis (404 `link_invalid`).
- **Token no fragmento** (`/reserva#<token>`): o navegador não envia fragmento ao servidor nem no `Referer`; a página o manda à API só no cabeçalho `Authorization`. Assim ele não aparece em logs de acesso do site nem da API. Página `/reserva` com CSP por nonce, `Referrer-Policy: no-referrer`, `noindex`, `no-store`.
- **Regras únicas**: `client_cancel_refusal`/`client_reschedule_refusal` no serviço são usadas pela página e pelas ações com ator `client`, então a tela nunca oferece o que o serviço recusa. Códigos mais precisos: reserva em processamento passou de `within_24h` para `in_progress`.
- **Reagendamento troca o link**: a nova reserva recebe link próprio na resposta (e no aviso `manage_link` quando o WhatsApp existir).
- **Limite por link** em Redis (contador por hash do token); se o Redis falhar, a requisição passa: o limite protege a cota do Google, e o token não é adivinhável.
- **Equipe pode gerar o link no painel** para enviar à mão enquanto o canal automático não existe (auditado).
- **Deadlock na restrição de exclusão** (descoberto nesta etapa, vindo da T08a): inserções simultâneas no mesmo horário podem se esperar mutuamente e o PostgreSQL aborta uma (40P01). Reservar e reagendar repetem a transação até 3 vezes em deadlock/serialização; na repetição a perdedora vê a vencedora e recebe `slot_unavailable` em vez de erro 503. Violação de restrição nunca é repetida.

## ADR-017 — WhatsApp pela Evolution: webhook, modo humano e envio revalidado (T09)

- **Quem escreveu um `fromMe`**: a Evolution entrega mensagens enviadas pela API como `messages.upsert` com `fromMe: true`, igual às digitadas no celular (confirmado na issue #1340 do projeto). Regra: é do bot só se o `key.id` for um id devolvido por um envio nosso; caso contrário, é da equipe e a conversa entra em **modo humano** (sem retomada por tempo). Enquanto um envio nosso está em andamento, um `fromMe` desconhecido fica `unknown`. Ele vira equipe assim que o envio termina com outro id, ou após 60 s, e nenhum envio automático sai enquanto isso. Base a validar na PoC: o id da resposta do envio é o mesmo do eco.
- **Comandos** só valem vindos do número da clínica (`fromMe`): `#bot` devolve ao bot e zera o fluxo; `#pausa`/`#humano` pausa. `#bot` enviado pela cliente não tem efeito. Fallback do plano já incluído.
- **Versão da conversa**: cada mensagem da cliente e cada troca de modo incrementa a versão; toda resposta ou aviso confere modo e versão logo antes do envio (ADR-008). Resposta gerada para uma versão antiga é descartada.
- **Avisos de reserva em modo humano não são enviados** (nota `human_mode` no outbox). É a leitura estrita da ADR-008; a clínica deve confirmar se lembretes devem sair mesmo com a equipe na conversa. `human_handoff` (problema com o horário) coloca a conversa em modo humano.
- **Fluxo determinístico por números** sobre o catálogo publicado: menu → área → procedimento (descrição, objetivos, duração, preço conforme regra) → pergunta sobre condição de saúde (“sim” vai para a equipe sem pedir detalhes) → profissional → dia → horário → nome → confirmação → `create_hold` idempotente por conversa+escolha. Menção a saúde (lista conservadora de termos), pedido de atendente, horário próximo demais, agenda indisponível ou procedimento de avaliação vão para a equipe. A IA (T10) poderá interpretar texto livre, mas não decide preço, horário nem regra.
- **Privacidade**: texto da cliente fica no banco só até ser lido; resposta do bot fica só até ser entregue (reenvio após queda, até 30 min e se a conversa não mudou); avisos são remontados a partir da reserva. Nome digitado para a reserva fica no estado da conversa só até a reserva ser criada. Logs sem telefone, id de chat nem texto (testado).
- **Webhook**: autenticação por `Authorization: Bearer <token>` configurado como cabeçalho do webhook na instância, comparado em tempo constante e verificado antes de qualquer outra dependência; instância conferida; corpo limitado a 1 MB; grupos, status, canais e histórico com mais de 24 h ignorados; cada `key.id` registrado uma vez (reentrega não gera nova resposta). Resposta rápida; a resposta ao cliente roda em segundo plano e o worker varre o que ficar pendente.
- **Conexão**: `connection.update`/`qrcode.updated` atualizam `integration_states`; qualquer estado diferente de `open` aparece como aviso no painel. Reconexão é manual e restrita (`RUNBOOK-WHATSAPP.md`).
- **Textos** (`whatsapp/texts.py`) são rascunhos para aprovação da clínica; dados de pagamento do sinal não são inventados: a mensagem diz que a equipe enviará os dados.

## ADR-018 — Camada de IA desligada por padrão, com fronteira estreita (T10)

- **Desligada até a avaliação de minimização** (ADR-007): `LUMINI_AI_ENABLED=false` por padrão. Sem ela, o bot é o fluxo determinístico da T09. Ligar exige rodar a bancada sintética com o provedor escolhido e aprovar o resultado (vazamentos, rotas de saúde, acerto por faixa de confiança).
- **Decisões locais antes de qualquer modelo**: STOP, menção a saúde (lista conservadora) e pedido de atendente são decididos sem modelo. O texto restante passa por redação (e-mail, link, documento, CEP, telefone, números longos, perfis); se algo identificável sobrar, a chamada não acontece. Nomes podem sobreviver: é minimização, não anonimização.
- **Onde o modelo entra**: só quando a pessoa escreve texto livre em menu, área, lista ou detalhe de procedimento; nunca no nome, na confirmação ou na escolha de horário. Classificador devolve `intent`/`service_id`/`confidence`; `service_id` precisa estar no catálogo publicado. Confiança alta segue a rota; média pergunta “Você está falando de X?”; baixa cai no caminho numérico. Limiares 0,85/0,6 **não calibrados**.
- **Redator** só explica um procedimento a partir dos fatos aprovados e das restrições de comunicação internas; a saída é descartada (nunca editada) se não for `grounded`, se tiver promessa/diagnóstico/adequação individual, se citar número ausente dos fatos ou se for longa. Fallback: “não tenho essa informação aprovada” + oferta da equipe.
- **Provedor**: adaptador OpenAI-compatível (`/chat/completions`, JSON, temperatura 0), que atende DeepSeek; modelos por configuração (os nomes da DeepSeek mudaram em 2026). O adaptador específico do **Jev** fica pendente: a documentação pública (Swagger) não pôde ser lida sem navegador, e não vamos supor a API. Classificador e redator podem apontar para modelos diferentes.
- **Contabilidade** (ADR-009): `ai_calls` guarda finalidade, modelo, resultado, latência e tokens; nunca texto, ids de conversa ou prompts. Custo será calculado com a tabela de preços vigente no momento da medição.
