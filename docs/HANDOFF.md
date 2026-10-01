# Handoff Lumini — atualizado a cada tarefa

Atualizado em 2026-10-01 ao concluir o **backend de T07** (Claude, retomando Codex). **Codex parou por limite de uso** às 11:00–11:02 (volta em 2026-10-04 17:40); confirmado pelos logs da sessão Codex que nenhum agente estava gravando na retomada. Confira processos/Git antes de assumir: esta informação é um snapshot. IDE: **VS Code**, backend Python/FastAPI.

## Próximo ponto de retomada

Próxima tarefa: **T07b — painel administrativo do catálogo** (frontend). O usuário já autorizou desenvolver conforme `PLANO.md`; não repetir grill-me nem pedir aprovação de novo para trabalho local desse escopo.

1. Conferir `git status`, `git log -1` e processos. **As mudanças de T07 estão no working tree, não commitadas** (aguardando o usuário pedir commit). Baseline commitado: `fe29e3c`.
2. Construir a página do painel (ex.: `frontend/src/app/admin/`) usando `frontend/src/lib/admin` (cliente com allowlist de rotas, decoders, `AdminSession` em memória, mensagens de erro em PT-BR). Login via Google Identity Services: token só em memória, nunca em storage/cookie/URL/log. Ajustar CSP/headers do Next para o script/iframe do GIS. Sem `NEXT_PUBLIC_GOOGLE_CLIENT_ID`/`NEXT_PUBLIC_API_BASE_URL` válidos, a página mostra estado "não configurado" (não inventar fallback).
3. Validar com backend local + verificador injetado/fake somente em teste; o login Google real continua **pendente** até existir Client ID de teste da clínica. Rodar `npm run build` só após encerrar/combinar o preview da porta 3000 (ver abaixo).
4. Depois: T08 (reservas transacionais/outbox/Calendar contratual) e T09 (PoC Evolution, precisa de instância própria).

## Contexto aprovado

O usuário encerrou grill-me, aprovou o plano em `PLANO.md`, alterou backend para Python/FastAPI e pediu continuidade escrita por tarefa. Regras permanentes em `../AGENTS.md`; decisões em `DECISOES.md` (novas: ADR-010 auth por ID token, ADR-011 catálogo serializado/versionado). Contrato da API em `API-ADMIN.md`. Projeto exclusivo em `/home/usuario/projects/lumini-clinica`; não usar o repositório Tecnoarte.

## Estado comprovado

- **Real local:** backend com **117 unitários + 55 integrações** PostgreSQL/Redis locais (zero skips/warnings com `-W error`); migração `0002_catalog_workflow` com roundtrip e `alembic check` sem drift; auth Google verificada **offline** com chaves RSA sintéticas (assinatura, claims, allowlist, falha fechada); fluxo de catálogo completo por HTTP contra PostgreSQL real (rascunho → aprovação por profissional/revisão → publicação; edição/credencial revogam; trava advisory provada com segunda conexão). Frontend: lint/typecheck verdes; preview estático em produção local.
- **Mock/sintético:** verificador/certificados Google nos testes; principal administrativo injetado nos testes de catálogo.
- **Apenas preparado:** CI com serviços sintéticos (sem execução remota); `frontend/src/lib/admin` (sem página que o use).
- **Não iniciado:** painel (UI), login Google real, Google Calendar, Evolution, IA, notificações, reservas/agendamento, deploy.
- Nenhuma credencial de fornecedor foi carregada/copiada; nenhum fornecedor externo foi chamado.

## Atenção para o usuário (afeta configuração futura)

- E-mails da allowlist precisam ser `@gmail.com` ou Google Workspace. Conta Google criada com e-mail de outro provedor (ex.: Yahoo) é recusada de propósito (ADR-010).
- Cada aprovadora precisa estar em `LUMINI_REVIEWER_ASSIGNMENTS` ligada ao UUID da profissional; verificação de credencial é ato humano registrado, não consulta ao conselho.
- Catálogo público não mostra registro de conselho até haver campo público revisado.

## Operação e processos ativos

- Sessão Claude: `claude --remote-control Lumini --no-chrome --ide` (PID 579918, iniciada pelo Codex em PTY), VS Code conectado via `/ide`. URL remota fora do Git.
- Frontend preview: `next start` em `http://127.0.0.1:3000` (PID 586398, iniciado pelo Codex). `next build` sobrescreveria `.next` com ele no ar.
- PostgreSQL 15.19 (`127.0.0.1:55432`, banco `lumini_foundation_test`, role sintética `lumini_test`, auth trust só em loopback; PID 600452) e Redis 7.0.15 (`127.0.0.1:56379`; PID 600459), religados pelo Codex a partir de `/tmp/lumini-services.j2gMAS`. Banco está na migração **0002**, tabelas vazias. Não é infraestrutura permanente.
- Integração: `LUMINI_INTEGRATION_DATABASE_URL=postgresql://lumini_test@127.0.0.1:55432/lumini_foundation_test LUMINI_INTEGRATION_REDIS_URL=redis://127.0.0.1:56379/0 make backend-integration` (só esta máquina; sem segredo).
- uv 0.12.21 em `.tools/`, Python 3.12.14 em `backend/.venv/`, Node 22 conforme `AMBIENTE.md`. Docker não instalado. PyCharm instalado anteriormente, não é mais requisito.

Detalhes/comandos em `AMBIENTE.md`; evidências em `TAREFAS.md` (entrada T07), `VALIDACAO-001.md`, `../backend/FOUNDATION_REPORT.md` e `../frontend/FOUNDATION_REPORT.md`. Git local branch `main`, sem remoto/push/deploy.

Pendências conhecidas: ESLint 9 EOL por incompatibilidade de peers com ESLint 10; custos/prazos ainda estimativas; contatos, credenciais profissionais, catálogo e materiais da clínica pendentes para produção (não bloqueiam desenvolvimento sintético).

## Suggested skills

- `handoff`: atualizar este documento e entregá-lo ao usuário em cada marco.
- `frontend-design` / `web-design-guidelines`: painel e, depois, landing premium/acolhedora com revisão de acessibilidade.
- `vercel-react-best-practices`: fronteiras server/client do App Router no painel.
- `security-review`: revisar o diff de T07/T07b antes do commit.

## Instrução sugerida para retomar com Claude

“Leia CLAUDE.md e docs/HANDOFF.md, confirme estado do Git e agentes ativos, continue a próxima tarefa pendente em docs/TAREFAS.md dentro do plano aprovado e atualize o handoff ao concluir cada tarefa. Diferencie local, mock e integração real. Não publique nem configure produção.”
