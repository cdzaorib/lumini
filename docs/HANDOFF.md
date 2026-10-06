# Handoff Lumini — atualizado a cada tarefa

Atualizado em **2026-10-06 — T12: preparação de produção, bloqueada por acessos/credenciais** (Codex). O usuário autorizou produção, repositório GitHub público e push, e confirmou **Vercel frontend + Supabase PostgreSQL + Railway API/worker/Redis**, preservando FastAPI e login Google (ADR-019). T11 continua implementada. **Nenhum deploy foi realizado**; Vercel foi criado/configurado. IDE: **VS Code**.

## T12 — estado atual e próximo passo

- **Real local:** auditoria e mapa de variáveis em `DEPLOY.md`; npm ci, lint, typecheck, build de produção, Ruff/format, mypy, 299 unitários, 189 integrações PostgreSQL/Redis e rodada final E2E **7/7, 111/111** passaram. Instalação backend `--frozen --no-dev` e startCommand da API em production passaram: live/ready 200, admin anônimo 401, docs/OpenAPI 404. Código da aplicação, dependências e lockfiles preservados.
- **Real na nuvem:** Vercel `lumini`, ID `prj_QLNtFWbhZcQbEY9xic5IqnMOZoVY`, equipe `cdzaoribs-projects`, root `frontend`, Next.js, Node `22.x`, install `npm ci`, build `npm run build`, output automático. Configuradas só `LUMINI_SITE_STAGE`/`LUMINI_SITE_PUBLIC` por ambiente; nenhum valor de credencial/URL inventado. Sem Git associado, deployment ou URL ainda.
- **Mock:** login Google, calendário, Evolution e dados E2E. Testes locais não validam Supabase/fornecedores reais.
- **Apenas preparado:** `frontend/vercel.json`/`.vercelignore`, `backend/railway.api.json`/`railway.worker.json`; build Railpack remoto não executado. `.vercel/` ignorado. Runbook de banco, variáveis, Google e domínio em `DEPLOY.md`.
- **Bloqueios:** CLI GitHub sem login válido, confirmado fora do sandbox; conector GitHub sem ferramenta de criação de repo; navegador recusou `github.com`; Railway desconectado (`USER_NOT_LOGGED_IN`). Supabase exclusivo autorizado, mas organização/custo exigidos pelo conector aguardam resposta. Nenhum segredo Lumini no ambiente da sessão.
- **Próximo passo:** usuário conclui `gh auth login -h github.com` fora do chat, conecta Railway e confirma se pode criar Supabase `lumini` na organização `relatorio de passagens`, em São Paulo. Depois verificar/confirmar custo, criar banco, configurar acesso seguro, inicializar migrações existentes, publicar API/worker, configurar variáveis reais, conectar GitHub e fazer produção/smoke. Google, calendários e insumos da clínica continuam necessários; nomes das variáveis faltantes em `DEPLOY.md`. Nenhuma compra/upgrade autorizado.
- **Git:** `main`, baseline `9ea0aa7`, sem remote/push; alterações só de configuração/documentação, com commit local após checks. Enviar o histórico existente ao repo público vazio após autenticação; nunca force push.
- **Processos conferidos:** Claude no VS Code PID 6805, sem alterações concorrentes observadas; não interrompido, nenhum subagente iniciado. Preview Next PID 142577/3000, PostgreSQL PID 13488/55432 e Redis PID 14385/56379 preservados. E2E/build na cópia `/tmp/lumini-release-validation`; API production local em `/tmp/lumini-backend-production`, processo de teste encerrado. Não deixar serviços de teste públicos.
- **Limitações:** primeira rodada E2E teve aviso intermitente de hidratação no site, não reproduzido no teste isolado nem na rodada final; rodada intermediária teve API 503 durante interferência do ambiente virtual de produção. Ambientes separados/restaurados antes da rodada final verde. Não presumir correção de produto; revalidar no deploy real. Execuções inicialmente bloqueadas pelo sandbox foram repetidas com permissão apropriada; cache de build bloqueado descartado só na cópia temporária.

**Escopo:** o plano integral em `PLANO-ORIGINAL.md` é o que deve ser entregue (o usuário reafirmou em 2026-10-01); a única troca aprovada é backend Python/FastAPI + Celery. `PLANO.md` é o resumo e lista os itens do texto integral a não perder.

## Próximo ponto de retomada

Tudo o que dependia só de código está construído e testado localmente, incluindo painel de conteúdo do site, métricas, comparecimento, aviso de sobreposição e E2E versionado (`make e2e`). **O que falta depende do usuário/clínica** e está item a item em `LANCAMENTO.md`. Ordem sugerida:

1. **Conteúdo e credenciais da clínica** (sem segredo): matriz de procedimentos, preços/sinais, credenciais e contatos de Munique e Michele (tudo pelo painel), conteúdo do site e instruções do sinal (aba Site), fotos autorizadas (ainda por código), aprovação dos textos do bot e das decisões abertas (3 h, sinal zero, lembretes em modo humano, conduta na sobreposição).
2. **Contas de teste** (configuradas fora do chat): Client ID Google do painel, conta de serviço do Google Agenda, instância Evolution com número de teste (PoC do `RUNBOOK-WHATSAPP.md`), provedor de IA para a bancada (só se a clínica quiser IA).
3. **Deploy autorizado na T12, aguardando acessos/configuração:** seguir `DEPLOY.md`; depois backups, revisão jurídica, piloto interno e aprovação final de conteúdo/indexação. Não há autorização de compra/upgrade.

Se o usuário pedir para continuar sem esses insumos, restam só itens que precisam de decisão ou insumo: edição dos textos do bot pelo painel (decidir se a clínica pode alterar textos sem revisão), fotos autorizadas no site, adaptador do Jev (documentação verificada), política de retenção de agendamentos/financeiro, upgrade do ESLint 10 quando os plugins suportarem.

Regras em `DECISOES.md` (ADR-013 a 018); contratos em `API-ADMIN.md`; operação em `RUNBOOK-WHATSAPP.md` e `RUNBOOK-BACKUP.md`; segurança em `SEGURANCA.md`; gates em `LANCAMENTO.md`; navegador em `e2e/README.md`.

## Contexto aprovado

O usuário encerrou grill-me, aprovou o plano em `PLANO.md`, alterou backend para Python/FastAPI e pediu continuidade escrita por tarefa. Regras permanentes em `../AGENTS.md`; decisões em `DECISOES.md` (ADR-010 auth por ID token, ADR-011 catálogo, ADR-012 CSP do painel, ADR-013 reservas, ADR-014 API/painel de reservas, ADR-015 worker/Google/reconciliação, ADR-016 link de autoatendimento, ADR-017 WhatsApp/modo humano, ADR-018 IA desligada por padrão). Contrato da API em `API-ADMIN.md`. Projeto exclusivo em `/home/usuario/projects/lumini-clinica`; não usar o repositório Tecnoarte.

## Estado comprovado

- **Real local:** backend com **299 unitários + 189 integrações** PostgreSQL/Redis locais (`-W error`, zero skips/warnings); `make e2e` com 7 cenários de navegador (111 etapas); canal WhatsApp com webhook simulado (`VALIDACAO-006.md`); site público, formulário de contato, chat no site e painel com abas Reservas/Contatos/Resumo/Agenda/Catálogo/Site/Integrações validados no Chrome (`VALIDACAO-007.md`); backup/restauração ensaiados; página da cliente `/reserva` validada no Chrome (`VALIDACAO-005.md`, 18/18); worker Celery com beat executou o tick real a cada 60 s (`VALIDACAO-004.md`); reconciliação de eventos alterados no Google; migrações até `0003_bookings` sem drift; trava por profissional/horário no banco provada em concorrência real; auth Google offline com chaves sintéticas; painel `/admin` com abas **Reservas / Agenda / Catálogo** validado de ponta a ponta no Chrome (`VALIDACAO-002.md` catálogo, `VALIDACAO-003.md` reservas/agenda, 26/26, CSP 0).
- **Mock/sintético:** provedor de IA (cliente roteirizado; IA desligada por padrão); Evolution (remetente falso e webhooks simulados); identidade injetada no backend de teste; stub do script do Google no navegador; **calendário em memória** nos testes e no E2E; **respostas do Google Calendar simuladas** nos testes do adaptador (chave de conta de serviço gerada na hora).
- **Apenas preparado:** CI com serviços sintéticos (sem execução remota). Adaptador Google real pronto, mas **nunca chamado** contra o Google: sem `LUMINI_GOOGLE_CALENDAR_CREDENTIALS`, rotas que consultam o calendário respondem 503 `calendar_not_configured` e o worker só expira reservas e agenda mensagens.
- **Não iniciado:** login Google real, Google Calendar real, instância Evolution real (PoC no runbook), provedor de IA real e benchmark, alerta de compromisso de terceiros sobre reserva confirmada, conteúdo real da landing, deploy.
- **Verificação de segredos:** gitleaks local verde no histórico (8 commits) com 3 falsos positivos da T08a fixados em `.gitleaksignore` por impressão digital; job de CI preparado (não executado remotamente).
- Nenhuma credencial de fornecedor foi carregada/copiada; nenhum fornecedor externo foi chamado com credencial.

## Atenção para o usuário (afeta configuração futura)

- E-mails da allowlist precisam ser `@gmail.com` ou Google Workspace. Conta Google criada com e-mail de outro provedor (ex.: Yahoo) é recusada de propósito (ADR-010).
- Cada aprovadora precisa estar em `LUMINI_REVIEWER_ASSIGNMENTS` ligada ao UUID da profissional (o UUID aparece após o cadastro no painel); verificação de credencial é ato humano registrado, não consulta ao conselho.
- Catálogo público mostra nome, categoria e registro de conselho das profissionais **verificadas** (identificação exigida pelo Cofen); restrições de comunicação e dados de revisão não são públicos.
- Para usar o painel de verdade: criar Client ID OAuth (tipo aplicação web) na conta Google da clínica com a origem do frontend, e configurar `NEXT_PUBLIC_GOOGLE_CLIENT_ID`, `NEXT_PUBLIC_API_BASE_URL` (HTTPS), `LUMINI_GOOGLE_CLIENT_ID`, `LUMINI_ADMIN_EMAILS`, `LUMINI_REVIEWER_ASSIGNMENTS` e `LUMINI_CORS_ORIGINS` — fora do Git, nunca pelo chat.
- Agenda: cada profissional precisa de um Google Agenda próprio cujo ID é cadastrado na aba Agenda; a conta de serviço da T08c precisará de permissão de edição nesse calendário. O calendário só pode ser trocado sem reservas ativas nele.
- **Google Agenda de verdade (passo a passo para a clínica, quando quiser ligar):** num projeto do Google Cloud da clínica, ativar a Google Calendar API, criar uma conta de serviço e uma chave JSON (organizações Workspace podem bloquear chaves pela política `iam.disableServiceAccountKeyCreation`); em cada Google Agenda de profissional, “Compartilhar com pessoas específicas” → e-mail da conta de serviço → “Fazer alterações nos eventos”; colocar o JSON em `LUMINI_GOOGLE_CALENDAR_CREDENTIALS` da API e do worker pelo gerenciador de segredos (nunca no Git nem no chat). Depois disso, fazer um teste controlado antes de abrir para clientes.
- **Link de autoatendimento:** configurar `LUMINI_MANAGE_LINK_SECRET` (valor aleatório com 32+ caracteres, só no gerenciador de segredos) e `LUMINI_PUBLIC_SITE_URL` (endereço HTTPS do site). Enquanto o WhatsApp automático não existir, a equipe gera o link no painel e envia pela conversa da clínica.
- **WhatsApp:** criar instância Evolution de teste (número de teste) para a PoC do `RUNBOOK-WHATSAPP.md` antes de usar o número oficial; configurar `LUMINI_EVOLUTION_*` na API e no worker pelo gerenciador de segredos. **Decidir:** lembretes devem sair mesmo com a equipe na conversa? (hoje não saem — ADR-017). **Aprovar** os textos do bot (`backend/src/lumini/whatsapp/texts.py`) e enviar as instruções reais do sinal (Pix) quando quiser que o bot as envie.
- Qualquer e-mail da allowlist pode confirmar sinal, cancelar e reagendar; a confirmação exige digitar o valor recebido e declarar que conferiu o crédito na conta.
- **Decisões de reserva para a clínica confirmar** (ADR-013): antecedência mínima de 3h para reservar online; sinal zero também exige confirmação humana; só serviços “agendamento direto” são reserváveis online (avaliações viram serviço próprio); eventos no Google sem nome/telefone da cliente.

## Operação e processos ativos

- Sessão Claude atual: extensão do VS Code. A antiga `claude --remote-control` (PID 579918) não existe mais após o reboot de 2026-10-05; para Remote Control, ver `AMBIENTE.md`.
- Frontend preview: `next start` em `http://127.0.0.1:3000` (next-server PID 142577), build da T11 (sem API configurada: site no ar, lista e formulário indisponíveis) **sem** variáveis do painel (`/admin` mostra “não configurado”). Novo `npm run build` exige parar este processo antes.
- PostgreSQL 15.19 (`127.0.0.1:55432`, banco `lumini_foundation_test`, role sintética `lumini_test`, trust só em loopback; PID 13488) e Redis 7.0.15 (`127.0.0.1:56379`; PID 14385), recriados a partir de `/tmp/lumini-services.aIKugt` (o diretório anterior sumiu no reboot). Banco na migração **0008**, tabelas vazias. Não é infraestrutura permanente; reboot apaga. Receita em `AMBIENTE.md`.
- Integração: `LUMINI_INTEGRATION_DATABASE_URL=postgresql://lumini_test@127.0.0.1:55432/lumini_foundation_test LUMINI_INTEGRATION_REDIS_URL=redis://127.0.0.1:56379/0 make backend-integration` (só esta máquina; sem segredo).
- `next dev` gera `frontend/AGENTS.md`/`CLAUDE.md` (versionados): ler a documentação do Next 16 em `frontend/node_modules/next/dist/docs/` antes de mexer em APIs do Next.
- Worker local (opcional, não fica rodando): `LUMINI_DATABASE_URL=postgresql://lumini_test@127.0.0.1:55432/lumini_foundation_test LUMINI_REDIS_URL=redis://127.0.0.1:56379/2 ../.tools/bin/uv run python -m lumini.worker` dentro de `backend/`.
- uv 0.12.21 em `.tools/`, Python 3.12.14 em `backend/.venv/`, Node 22 conforme `AMBIENTE.md`. Docker não instalado. PyCharm não é mais requisito.

Detalhes/comandos em `AMBIENTE.md`; evidências em `TAREFAS.md`, `VALIDACAO-001.md` a `VALIDACAO-008.md`, `SEGURANCA.md`, `LANCAMENTO.md`, `RUNBOOK-WHATSAPP.md`, `RUNBOOK-BACKUP.md`, `../backend/FOUNDATION_REPORT.md` e `../frontend/FOUNDATION_REPORT.md`. Git local branch `main`, sem remoto/push/deploy.

Pendências conhecidas: ESLint 9 EOL por incompatibilidade de peers com ESLint 10; custos/prazos ainda estimativas; contatos, credenciais profissionais, catálogo e materiais da clínica pendentes para produção (não bloqueiam desenvolvimento sintético); suíte E2E do painel continua fora do Git.

## Suggested skills

- `handoff`: atualizar este documento e entregá-lo ao usuário em cada marco.
- `security-review`: revisão completa antes do primeiro deploy autorizado.
- `web-design-guidelines`: auditoria de acessibilidade do site com conteúdo real.
- `frontend-design` / `web-design-guidelines`: landing premium/acolhedora com revisão de acessibilidade (fase da landing).

## Instrução sugerida para retomar com Claude

“Leia CLAUDE.md e docs/HANDOFF.md, confirme estado do Git e agentes ativos, continue a próxima tarefa pendente em docs/TAREFAS.md dentro do plano aprovado e atualize o handoff ao concluir cada tarefa. Diferencie local, mock e integração real. Não publique nem configure produção.”
