# Evidências do primeiro marco local

Data: 2026-10-01. Somente ambiente de desenvolvimento e dados sintéticos.

## Componentes

- Backend: ver `../backend/FOUNDATION_REPORT.md` para versões e checks. Fundação de API/recursos/catálogo/worker, sem lógica de reservas nem mutações administrativas.
- Frontend: ver `../frontend/FOUNDATION_REPORT.md` para versões, instalação limpa, lint/typecheck/build e auditoria de dependências.
- CI: `.github/workflows/checks.yml` preparado para checks e serviços PostgreSQL/Redis de teste. Não foi executado no GitHub; não existe remoto configurado.

## Navegador real

Production build local em `http://127.0.0.1:3000`. agent-browser 0.27.0 em sessão exclusiva `lumini-foundation`.

- Página carregou com conteúdo, heading e links corretos.
- Console e erros de página vazios; nenhum overlay de erro.
- Screenshots inspecionados visualmente em desktop (1280px) e mobile (390px).
- Sem overflow horizontal em 1280, 390 e 320px.
- `Tab` + `Enter` no link de pular conteúdo focou `main#conteudo`.
- Emulação de `prefers-reduced-motion: reduce` reconhecida pelo navegador.
- Meta robots `noindex, nofollow, nocache`; headers/robots.txt verificados pelo agente frontend.
- Apenas link externo real ao Base44; não há controles de agendamento/chat fictícios.
- Capturas temporárias são ignoradas pelo Git; não contêm dados de clientes.

Isto é verificação de uma prévia estática, não teste de acessibilidade completo nem validação da landing final.

## PostgreSQL/Redis locais reais

Na ausência de Docker/serviços instalados, pacotes Debian foram baixados e extraídos em diretório temporário exclusivo, sem instalar serviços de sistema. PostgreSQL 15.19; Redis 7.0.15. O pacote Redis security u9 retornou 404 no mirror; binários do pacote main u7 foram usados apenas no ensaio isolado com dados sintéticos. Esta versão não é uma decisão de produção.

Instâncias ouviram somente em loopback, portas 55432 e 56379; banco exclusivo `lumini_foundation_test`, role sintética `lumini_test`, sem dados reais.

- `alembic upgrade head`: sucesso.
- `alembic check`: `No new upgrade operations detected.`
- API real: `/health/live` retornou `alive` e `/health/ready` retornou `ready`, PostgreSQL e Redis `ok`.
- **14 testes opt-in reais passaram** (catálogo/constraints/defaults/FKs/readiness), sem skips; três tabelas sem registros ao final, inserts revertidos.
- Roundtrip da migração no banco efêmero: `downgrade base` → `upgrade head` → `alembic check`, sucesso sem drift. Somente banco criado nesta tarefa.
- Worker Celery iniciou com Redis local; primeira sondagem antes da prontidão não encontrou worker; segunda retornou um worker e `pong`. Isso comprova broker/controle, não execução de jobs de negócio (ainda inexistentes).

Não valida Railway, políticas de backup, alta disponibilidade, segurança de produção nem integrações Google/Evolution/IA.

## Claude e IDE

CLI 2.1.286 autenticado; terminal confirmou `/remote-control is active` e `Connected to Visual Studio Code`. Workspace da extensão é a pasta Lumini. Sessão aberta em PTY do Codex com vínculo ao VS Code; URL privada fora do Git. Não foram dadas tarefas de implementação ao Claude.

## Limitações que permanecem

- Autenticação/autorização e fluxo de conteúdo ainda não implementados.
- Calendar, Evolution, IA, agendamento e pagamentos não integrados.
- Conteúdo/credenciais profissionais/fotos/contatos reais pendentes.
- ESLint 9 compatível com peers atuais está EOL; documentado para atualização assim que plugins suportarem a linha nova.
- Dockerfile/containers e execução de CI remoto ainda não validados.
- Orçamento R$100–300 e estimativa de 4–6 semanas são hipóteses de planejamento.

## Revisão independente final

Revisão identificou e corrigiu dois defeitos de configuração: Kombu aceitava Redis TLS sem certificado obrigatório; construção dos clientes podia emitir valores brutos de querystring em erro. Agora o broker `rediss` exige certificado/hostname, URLs não podem desativar essas verificações, e construção Redis/SQLAlchemy/Alembic emite mensagem fixa sem cadeia sensível. Testes verificam o objeto Kombu e traceback completo. Não houve exposição de credenciais reais: cenários usaram apenas entradas sintéticas. Handshake TLS remoto não foi testado.

Resultado final: **30 unitários + 14 integrações reais locais**, sem skips ou warnings; Ruff/formatação/mypy/lockfile verdes. Frontend lint/typecheck/build verdes; não houve mudança frontend após esses checks. API e worker de ensaio encerrados normalmente; banco/Redis efêmeros também encerrados. Diretórios temporários e downloads foram preservados (não removidos). O frontend local, Claude e PyCharm permanecem disponíveis para o usuário.
