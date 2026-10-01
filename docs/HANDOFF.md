# Handoff Lumini — atualizado a cada tarefa

Atualizado em 2026-10-01 ao concluir **T07b — painel do catálogo** (Claude). Codex parado por limite de uso até 2026-10-04 17:40; nenhum outro agente gravando. Confira processos/Git antes de assumir: esta informação é um snapshot. IDE: **VS Code**, backend Python/FastAPI.

**Escopo:** o plano integral em `PLANO-ORIGINAL.md` é o que deve ser entregue (o usuário reafirmou em 2026-10-01); a única troca aprovada é backend Python/FastAPI + Celery. `PLANO.md` é o resumo e lista os itens do texto integral a não perder.

## Próximo ponto de retomada

Próxima tarefa: **T08 — reservas transacionais e contrato de calendário** (Fase 2). O usuário autorizou desenvolver conforme o plano; não repetir grill-me nem pedir aprovação de novo para trabalho local desse escopo. Commits locais estão autorizados ("pode alterar e seguir"); push/deploy/produção continuam exigindo autorização específica.

1. Conferir `git status`, `git log -1` e processos.
2. Modelar reservas com estados explícitos (ADR-008), `expires_at` persistido, idempotency keys, outbox e trava/restrição transacional por profissional+horário (não reutilizar a trava do catálogo, ADR-011). Duração + intervalo de 15min vêm do catálogo publicado.
3. Contrato de calendário atrás de adapter (fake em teste): consulta de disponibilidade, **evento temporário** ao reservar (passo 9 do plano), confirmação após sinal humano, remoção na expiração, reconciliação e falha conservadora sem atomicidade distribuída.
4. Confirmação de sinal humana e autenticada (rota admin), corrida com expiração na mesma transição condicional; janela mínima de 2h antes do atendimento; cancelamento/reagendamento >24h autoatendimento, ≤24h humano.
5. Testes de concorrência reais no PostgreSQL. Google Calendar real fica pendente até haver calendários de teste da clínica.
6. Pendência curta paralela: **T07c** verificação de segredos no CI.

## Contexto aprovado

O usuário encerrou grill-me, aprovou o plano em `PLANO.md`, alterou backend para Python/FastAPI e pediu continuidade escrita por tarefa. Regras permanentes em `../AGENTS.md`; decisões em `DECISOES.md` (novas: ADR-010 auth por ID token, ADR-011 catálogo serializado/versionado, ADR-012 CSP do painel). Contrato da API em `API-ADMIN.md`. Projeto exclusivo em `/home/usuario/projects/lumini-clinica`; não usar o repositório Tecnoarte.

## Estado comprovado

- **Real local:** backend com **121 unitários + 55 integrações** PostgreSQL/Redis locais (zero skips/warnings com `-W error`); migração `0002` com roundtrip e sem drift; auth Google verificada offline com chaves RSA sintéticas; fluxo de catálogo por HTTP contra PostgreSQL real. Painel `/admin` validado de ponta a ponta no Chrome (12/12 etapas, 0 violações de CSP, 0 erros de console) com API e banco reais e script do Google em stub; script real do Google carregou sob a CSP sem violações; build de produção verde (`VALIDACAO-002.md`).
- **Mock/sintético:** identidade injetada no backend de teste; stub do script do Google no navegador; principal injetado nos testes de catálogo.
- **Apenas preparado:** CI com serviços sintéticos (sem execução remota).
- **Não iniciado:** login Google real, Google Calendar, reservas/agendamento, Evolution, IA, notificações, landing completa, verificação de segredos no CI, deploy.
- Nenhuma credencial de fornecedor foi carregada/copiada; nenhum fornecedor externo foi chamado com credencial.

## Atenção para o usuário (afeta configuração futura)

- E-mails da allowlist precisam ser `@gmail.com` ou Google Workspace. Conta Google criada com e-mail de outro provedor (ex.: Yahoo) é recusada de propósito (ADR-010).
- Cada aprovadora precisa estar em `LUMINI_REVIEWER_ASSIGNMENTS` ligada ao UUID da profissional (o UUID aparece após o cadastro no painel); verificação de credencial é ato humano registrado, não consulta ao conselho.
- Catálogo público mostra nome, categoria e registro de conselho das profissionais **verificadas** (identificação exigida pelo Cofen); restrições de comunicação e dados de revisão não são públicos.
- Para usar o painel de verdade: criar Client ID OAuth (tipo aplicação web) na conta Google da clínica com a origem do frontend, e configurar `NEXT_PUBLIC_GOOGLE_CLIENT_ID`, `NEXT_PUBLIC_API_BASE_URL` (HTTPS), `LUMINI_GOOGLE_CLIENT_ID`, `LUMINI_ADMIN_EMAILS`, `LUMINI_REVIEWER_ASSIGNMENTS` e `LUMINI_CORS_ORIGINS` — fora do Git, nunca pelo chat.

## Operação e processos ativos

- Sessão Claude: `claude --remote-control Lumini --no-chrome --ide` (PID 579918, iniciada pelo Codex em PTY), VS Code conectado via `/ide`. URL remota fora do Git.
- Frontend preview: `next start` em `http://127.0.0.1:3000` (PID 624146; religado por esta sessão com o build de T07b, **sem** variáveis do painel, então `/admin` mostra “não configurado”). Novo `npm run build` exige parar este processo antes.
- PostgreSQL 15.19 (`127.0.0.1:55432`, banco `lumini_foundation_test`, role sintética `lumini_test`, auth trust só em loopback; PID 600452) e Redis 7.0.15 (`127.0.0.1:56379`; PID 600459), a partir de `/tmp/lumini-services.j2gMAS`. Banco na migração **0002**, tabelas vazias. Não é infraestrutura permanente.
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
