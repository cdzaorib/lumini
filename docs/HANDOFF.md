# Handoff Lumini — atualizado a cada tarefa

Atualizado em 2026-10-01 ao concluir **T07b — painel do catálogo** (Claude). Codex parado por limite de uso até 2026-10-04 17:40; nenhum outro agente gravando. Confira processos/Git antes de assumir: esta informação é um snapshot. IDE: **VS Code**, backend Python/FastAPI.

**Escopo:** o plano integral em `PLANO-ORIGINAL.md` é o que deve ser entregue (o usuário reafirmou em 2026-10-01); a única troca aprovada é backend Python/FastAPI + Celery. `PLANO.md` é o resumo e lista os itens do texto integral a não perder.

## Próximo ponto de retomada

Próxima tarefa: **T08b — API administrativa e painel de reservas/agenda.** O usuário autorizou seguir o plano até acabarem os créditos da sessão, com commits locais; push/deploy/produção continuam exigindo autorização específica.

1. Conferir `git status`, `git log -1` e processos.
2. Backend: rotas `/api/admin/` para agenda da profissional (`calendar_id` + regras semanais, PUT com `expected_revision`, sem tocar na verificação de credencial), prévia de horários, lista de reservas (nome/telefone só para equipe), confirmar sinal (valor + versão), cancelar, resolver conflito. Mapear `BookingError` para 403/404/409/422; sincronizar calendário em segundo plano após mutação é opcional — o worker (T08c) é o caminho confiável.
3. Painel: seções “Agenda” (por profissional) e “Reservas” (pendentes de sinal com prazo, confirmadas, conflitos), mesma CSP e padrões de foco/mensagens de `/admin`.
4. Depois: T08c (worker Celery beat + adaptador Google com conta de serviço) e T08d (links de autoatendimento).

Regras de reserva em `DECISOES.md` (ADR-013); código em `backend/src/lumini/booking/`.

## Contexto aprovado

O usuário encerrou grill-me, aprovou o plano em `PLANO.md`, alterou backend para Python/FastAPI e pediu continuidade escrita por tarefa. Regras permanentes em `../AGENTS.md`; decisões em `DECISOES.md` (novas: ADR-010 auth por ID token, ADR-011 catálogo serializado/versionado, ADR-012 CSP do painel). Contrato da API em `API-ADMIN.md`. Projeto exclusivo em `/home/usuario/projects/lumini-clinica`; não usar o repositório Tecnoarte.

## Estado comprovado

- **Real local:** backend com **130 unitários + 91 integrações** PostgreSQL/Redis locais (zero skips/warnings com `-W error`); migrações até `0003_bookings` com roundtrip e sem drift; núcleo de reservas com trava por profissional/horário no banco provada em concorrência real; auth Google offline com chaves sintéticas; catálogo e painel `/admin` validados de ponta a ponta no Chrome (`VALIDACAO-002.md`).
- **Mock/sintético:** identidade injetada no backend de teste; stub do script do Google no navegador; principal injetado nos testes de catálogo; **calendário em memória** nos testes de reserva.
- **Apenas preparado:** CI com serviços sintéticos (sem execução remota).
- **Não iniciado:** login Google real, Google Calendar real, API/painel de reservas, worker agendado, Evolution, IA, envio de notificações, landing completa, deploy.
- **Verificação de segredos:** gitleaks local verde; job de CI preparado (não executado remotamente).
- Nenhuma credencial de fornecedor foi carregada/copiada; nenhum fornecedor externo foi chamado com credencial.

## Atenção para o usuário (afeta configuração futura)

- E-mails da allowlist precisam ser `@gmail.com` ou Google Workspace. Conta Google criada com e-mail de outro provedor (ex.: Yahoo) é recusada de propósito (ADR-010).
- Cada aprovadora precisa estar em `LUMINI_REVIEWER_ASSIGNMENTS` ligada ao UUID da profissional (o UUID aparece após o cadastro no painel); verificação de credencial é ato humano registrado, não consulta ao conselho.
- Catálogo público mostra nome, categoria e registro de conselho das profissionais **verificadas** (identificação exigida pelo Cofen); restrições de comunicação e dados de revisão não são públicos.
- Para usar o painel de verdade: criar Client ID OAuth (tipo aplicação web) na conta Google da clínica com a origem do frontend, e configurar `NEXT_PUBLIC_GOOGLE_CLIENT_ID`, `NEXT_PUBLIC_API_BASE_URL` (HTTPS), `LUMINI_GOOGLE_CLIENT_ID`, `LUMINI_ADMIN_EMAILS`, `LUMINI_REVIEWER_ASSIGNMENTS` e `LUMINI_CORS_ORIGINS` — fora do Git, nunca pelo chat.

- **Decisões de reserva para a clínica confirmar** (ADR-013): antecedência mínima de 3h para reservar online; sinal zero também exige confirmação humana; só serviços “agendamento direto” são reserváveis online (avaliações viram serviço próprio); eventos no Google sem nome/telefone da cliente.

## Operação e processos ativos

- Sessão Claude: `claude --remote-control Lumini --no-chrome --ide` (PID 579918, iniciada pelo Codex em PTY), VS Code conectado via `/ide`. URL remota fora do Git.
- Frontend preview: `next start` em `http://127.0.0.1:3000` (PID 624146; religado por esta sessão com o build de T07b, **sem** variáveis do painel, então `/admin` mostra “não configurado”). Novo `npm run build` exige parar este processo antes.
- PostgreSQL 15.19 (`127.0.0.1:55432`, banco `lumini_foundation_test`, role sintética `lumini_test`, auth trust só em loopback; PID 600452) e Redis 7.0.15 (`127.0.0.1:56379`; PID 600459), a partir de `/tmp/lumini-services.j2gMAS`. Banco na migração **0003**, tabelas vazias. Não é infraestrutura permanente.
- Integração: `LUMINI_INTEGRATION_DATABASE_URL=postgresql://lumini_test@127.0.0.1:55432/lumini_foundation_test LUMINI_INTEGRATION_REDIS_URL=redis://127.0.0.1:56379/0 make backend-integration` (só esta máquina; sem segredo).
- `next dev` gera `frontend/AGENTS.md`/`CLAUDE.md` (versionados): ler a documentação do Next 16 em `frontend/node_modules/next/dist/docs/` antes de mexer no frontend.
- uv 0.12.21 em `.tools/`, Python 3.12.14 em `backend/.venv/`, Node 22 conforme `AMBIENTE.md`. Docker não instalado. PyCharm não é mais requisito.

Detalhes/comandos em `AMBIENTE.md`; evidências em `TAREFAS.md`, `VALIDACAO-001.md`, `VALIDACAO-002.md`, `../backend/FOUNDATION_REPORT.md` e `../frontend/FOUNDATION_REPORT.md`. Git local branch `main`, sem remoto/push/deploy.

Pendências conhecidas: ESLint 9 EOL por incompatibilidade de peers com ESLint 10; custos/prazos ainda estimativas; contatos, credenciais profissionais, catálogo e materiais da clínica pendentes para produção (não bloqueiam desenvolvimento sintético).

## Suggested skills

- `handoff`: atualizar este documento e entregá-lo ao usuário em cada marco.
- `frontend-design` / `web-design-guidelines`: painel e, depois, landing premium/acolhedora com revisão de acessibilidade.
- `vercel-react-best-practices`: fronteiras server/client do App Router no painel.
- `security-review`: revisar o diff de T07/T07b antes do commit.

## Instrução sugerida para retomar com Claude

“Leia CLAUDE.md e docs/HANDOFF.md, confirme estado do Git e agentes ativos, continue a próxima tarefa pendente em docs/TAREFAS.md dentro do plano aprovado e atualize o handoff ao concluir cada tarefa. Diferencie local, mock e integração real. Não publique nem configure produção.”
