# Handoff Lumini — atualizado a cada tarefa

Atualizado em 2026-10-05 ao concluir **T08d — autoatendimento por link seguro** (Claude, sessão no VS Code). O usuário pediu para seguir **até a etapa 10** (T09 e T10 na sequência). Nenhum outro agente gravando. Confira processos/Git antes de assumir: esta informação é um snapshot. IDE: **VS Code**, backend Python/FastAPI.

**Escopo:** o plano integral em `PLANO-ORIGINAL.md` é o que deve ser entregue (o usuário reafirmou em 2026-10-01); a única troca aprovada é backend Python/FastAPI + Celery. `PLANO.md` é o resumo e lista os itens do texto integral a não perder.

## Próximo ponto de retomada

Próxima tarefa: **T09 — WhatsApp (Evolution) e modo humano**, sem instância de teste: construir e validar com webhooks simulados, marcando a PoC real como pendente. Depois **T10** (IA com conteúdo aprovado, experiência pública/chat, checklist de piloto). Commits locais autorizados; push/deploy/produção exigem autorização específica.

1. Conferir `git status`, `git log -1` e processos.
2. T09: adaptador Evolution (envio de texto; segredo de webhook; sem texto do provedor em erros/logs), webhook autenticado e idempotente, registro de mensagens enviadas pelo bot (id) para distinguir mensagem manual (`fromMe` sem id nosso) — `fromMe` sozinho não prova humano (ADR-009) —, modo humano persistido com versão da conversa, `#bot` só de remetente autorizado, invalidação de respostas pendentes, fallback de pausa explícita pelo WhatsApp (plano integral), `Notifier` real para o outbox com textos aprovados e o link da T08d, estado da conexão (`connection.update`) e alerta de desconexão.
3. Mensagens com dados de contato nunca vão para logs; corpo de mensagens não é guardado além do mínimo (ADR-007/009).

Regras de reserva em `DECISOES.md` (ADR-013 a 016); contrato em `API-ADMIN.md`; código em `backend/src/lumini/booking/`.

## Contexto aprovado

O usuário encerrou grill-me, aprovou o plano em `PLANO.md`, alterou backend para Python/FastAPI e pediu continuidade escrita por tarefa. Regras permanentes em `../AGENTS.md`; decisões em `DECISOES.md` (ADR-010 auth por ID token, ADR-011 catálogo, ADR-012 CSP do painel, ADR-013 reservas, ADR-014 API/painel de reservas, ADR-015 worker/Google/reconciliação, ADR-016 link de autoatendimento). Contrato da API em `API-ADMIN.md`. Projeto exclusivo em `/home/usuario/projects/lumini-clinica`; não usar o repositório Tecnoarte.

## Estado comprovado

- **Real local:** backend com **211 unitários + 140 integrações** PostgreSQL/Redis locais (`-W error`, zero skips/warnings, **20 rodadas seguidas estáveis** após corrigir deadlock intermitente); página da cliente `/reserva` validada no Chrome (`VALIDACAO-005.md`, 18/18); worker Celery com beat executou o tick real a cada 60 s (`VALIDACAO-004.md`); reconciliação de eventos alterados no Google; migrações até `0003_bookings` sem drift; trava por profissional/horário no banco provada em concorrência real; auth Google offline com chaves sintéticas; painel `/admin` com abas **Reservas / Agenda / Catálogo** validado de ponta a ponta no Chrome (`VALIDACAO-002.md` catálogo, `VALIDACAO-003.md` reservas/agenda, 26/26, CSP 0).
- **Mock/sintético:** identidade injetada no backend de teste; stub do script do Google no navegador; **calendário em memória** nos testes e no E2E; **respostas do Google Calendar simuladas** nos testes do adaptador (chave de conta de serviço gerada na hora).
- **Apenas preparado:** CI com serviços sintéticos (sem execução remota). Adaptador Google real pronto, mas **nunca chamado** contra o Google: sem `LUMINI_GOOGLE_CALENDAR_CREDENTIALS`, rotas que consultam o calendário respondem 503 `calendar_not_configured` e o worker só expira reservas e agenda mensagens.
- **Não iniciado:** login Google real, Google Calendar real, envio automático do link de autoatendimento, Evolution, IA, envio de notificações (ficam pendentes no outbox), alerta de compromisso de terceiros sobre reserva confirmada, landing completa, deploy.
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
- Qualquer e-mail da allowlist pode confirmar sinal, cancelar e reagendar; a confirmação exige digitar o valor recebido e declarar que conferiu o crédito na conta.
- **Decisões de reserva para a clínica confirmar** (ADR-013): antecedência mínima de 3h para reservar online; sinal zero também exige confirmação humana; só serviços “agendamento direto” são reserváveis online (avaliações viram serviço próprio); eventos no Google sem nome/telefone da cliente.

## Operação e processos ativos

- Sessão Claude atual: extensão do VS Code. A antiga `claude --remote-control` (PID 579918) não existe mais após o reboot de 2026-10-05; para Remote Control, ver `AMBIENTE.md`.
- Frontend preview: `next start` em `http://127.0.0.1:3000` (next-server PID 47816), build da T08d **sem** variáveis do painel (`/admin` mostra “não configurado”). Novo `npm run build` exige parar este processo antes.
- PostgreSQL 15.19 (`127.0.0.1:55432`, banco `lumini_foundation_test`, role sintética `lumini_test`, trust só em loopback; PID 13488) e Redis 7.0.15 (`127.0.0.1:56379`; PID 14385), recriados a partir de `/tmp/lumini-services.aIKugt` (o diretório anterior sumiu no reboot). Banco na migração **0003**, tabelas vazias. Não é infraestrutura permanente; reboot apaga. Receita em `AMBIENTE.md`.
- Integração: `LUMINI_INTEGRATION_DATABASE_URL=postgresql://lumini_test@127.0.0.1:55432/lumini_foundation_test LUMINI_INTEGRATION_REDIS_URL=redis://127.0.0.1:56379/0 make backend-integration` (só esta máquina; sem segredo).
- `next dev` gera `frontend/AGENTS.md`/`CLAUDE.md` (versionados): ler a documentação do Next 16 em `frontend/node_modules/next/dist/docs/` antes de mexer em APIs do Next.
- Worker local (opcional, não fica rodando): `LUMINI_DATABASE_URL=postgresql://lumini_test@127.0.0.1:55432/lumini_foundation_test LUMINI_REDIS_URL=redis://127.0.0.1:56379/2 ../.tools/bin/uv run python -m lumini.worker` dentro de `backend/`.
- uv 0.12.21 em `.tools/`, Python 3.12.14 em `backend/.venv/`, Node 22 conforme `AMBIENTE.md`. Docker não instalado. PyCharm não é mais requisito.

Detalhes/comandos em `AMBIENTE.md`; evidências em `TAREFAS.md`, `VALIDACAO-001.md` a `VALIDACAO-005.md`, `../backend/FOUNDATION_REPORT.md` e `../frontend/FOUNDATION_REPORT.md`. Git local branch `main`, sem remoto/push/deploy.

Pendências conhecidas: ESLint 9 EOL por incompatibilidade de peers com ESLint 10; custos/prazos ainda estimativas; contatos, credenciais profissionais, catálogo e materiais da clínica pendentes para produção (não bloqueiam desenvolvimento sintético); suíte E2E do painel continua fora do Git.

## Suggested skills

- `handoff`: atualizar este documento e entregá-lo ao usuário em cada marco.
- `security-review`: revisar o webhook da Evolution (autenticação, replay, entrada não confiável) antes do commit da T09.
- `frontend-design` / `web-design-guidelines`: landing e chat da T10.
- `frontend-design` / `web-design-guidelines`: landing premium/acolhedora com revisão de acessibilidade (fase da landing).

## Instrução sugerida para retomar com Claude

“Leia CLAUDE.md e docs/HANDOFF.md, confirme estado do Git e agentes ativos, continue a próxima tarefa pendente em docs/TAREFAS.md dentro do plano aprovado e atualize o handoff ao concluir cada tarefa. Diferencie local, mock e integração real. Não publique nem configure produção.”
