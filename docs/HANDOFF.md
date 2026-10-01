# Handoff Lumini — atualizado a cada tarefa

Atualizado em 2026-10-01 ao concluir T06. **Primeiro marco local concluído; agentes de implementação encerraram suas tarefas.** Confira processos/Git antes de assumir, pois esta informação é um snapshot.

## Próximo ponto de retomada

Próxima tarefa: **T07 — autorização administrativa e aprovação do catálogo**. O usuário já autorizou desenvolver conforme `PLANO.md`; não repetir grill-me nem pedir aprovação novamente para trabalho local desse escopo.

1. Conferir `git status`, `git log -1` e processos; ler os relatórios vinculados abaixo.
2. Implementar identidade/autorização com allowlist no backend e contrato Google login. Sem conta/configuração de teste, validar com fixtures sintéticas e manter integração real explicitamente pendente; não criar bypass de produção.
3. Criar serviço de domínio de catálogo/aprovação: exigir conteúdo, profissional habilitado, revisão e identidade autenticada; alterar conteúdo revoga aprovação anterior. Só então expor mutações administrativas.
4. Atualizar este handoff e `TAREFAS.md` ao concluir cada tarefa. T08 tratará reservas concorrentes/outbox/Calendar; T09 precisa da PoC Evolution com instância própria.

## Contexto aprovado

O usuário encerrou grill-me, aprovou o plano em `PLANO.md`, alterou backend para Python/FastAPI e pediu continuidade escrita por tarefa. Regras permanentes em `../AGENTS.md`; decisões em `DECISOES.md`. Não repetir perguntas já resolvidas. Projeto exclusivo em `/home/usuario/projects/lumini-clinica`; não usar o repositório Tecnoarte.

## Estado comprovado

- Real local: backend testado (**30 unitários + 14 integrações reais**, zero skips/warnings), frontend buildado/lintado/tipado e revisado no navegador, migração aplicada/roundtrip sem drift, readiness PostgreSQL/Redis, Celery com `pong`, conexão Claude/VS Code e Remote Control, PyCharm instalado/iniciado.
- Mock: probes nos testes unitários. Separadamente há integrações reais locais comprovadas, sem afirmar validação de fornecedores de nuvem.
- Revisão final: TLS Redis do worker com certificado/hostname obrigatórios e erros de criação sanitizados; regressões aprovadas. Handshake TLS remoto não validado.
- Apenas preparado: CI com serviços sintéticos (sem execução remota).
- Não iniciado: login Google, Google Calendar, Evolution, IA, notificações, reservas/agendamento e deploy.
- Nenhuma credencial de fornecedor foi carregada/copiadada e nenhum fornecedor foi testado nesta tarefa.

## Operação e bloqueios conhecidos

Claude Code 2.1.286 autenticado e Remote Control **ativo**, visto no terminal; VS Code conectado à pasta Lumini via `/ide`. Sessão aguardando usuário, sem tarefa concorrente. Processo iniciado por Codex em PTY (session_id61380, PID579918), não terminal integrado do VS Code; vínculo com IDE confirmado. URL de acesso não incluída no Git. PyCharm2026.2.3 instalado e iniciado (PID591966); primeiro uso/seleção do interpretador não verificados na UI. uv0.12.21 em `.tools/` e Python3.12.14 em `backend/.venv/`, ambos isolados. Docker não instalado. Os contatos, credenciais profissionais, catálogo e materiais da clínica continuam pendentes para produção, mas não bloqueiam desenvolvimento com fixtures sintéticas.

Frontend de produção local mantido em `http://127.0.0.1:3000` (session_id35558) para revisão. API8000, worker, PostgreSQL55432, Redis56379 e navegador automatizado foram encerrados. Diretórios temporários preservados: `/tmp/lumini-services.j2gMAS` (banco sintético/pacotes) e `/tmp/lumini-pycharm.LEEI77` (download conferido). Não depender desses diretórios para ambiente permanente.

Detalhes/comandos em `AMBIENTE.md`; evidências em `VALIDACAO-001.md`, `../backend/FOUNDATION_REPORT.md` e `../frontend/FOUNDATION_REPORT.md`. `make check` executa checks locais (ativar Node22 antes); `make backend-integration` exige URLs explícitas de serviços isolados e banco com sufixo `_test`. Git local branch `main`, sem remoto/push/deploy. Use `git log -1` para identificar o snapshot.

O frontend é uma prévia estática: **não é a landing final e não contém bot/agendamento/painel**. Backend tem apenas saúde e catálogo no banco; Google login não implementado. O plano inteiro não está concluído. Pendência de tooling: ESLint9 EOL por incompatibilidade dos peers com ESLint10; audit npm retornou zero vulnerabilidades no momento, não garantia de segurança futura. Custo e prazos ainda são estimativas.

## Suggested skills

- `handoff`: atualizar este documento e entregá-lo ao usuário em cada marco.
- `nextjs`: convenções do App Router e fronteiras server/client.
- `frontend-design`: design da landing premium/acolhedora quando chegar a fase visual.
- `web-design-guidelines`: revisão de acessibilidade antes do piloto.
- `vercel:agent-browser-verify`: validação de interface local quando o navegador estiver disponível.

## Instrução sugerida para retomar com Claude

“Leia CLAUDE.md e docs/HANDOFF.md, confirme estado do Git e agentes ativos, continue a próxima tarefa pendente em docs/TAREFAS.md dentro do plano aprovado e atualize o handoff ao concluir cada tarefa. Diferencie local, mock e integração real. Não publique nem configure produção.”
