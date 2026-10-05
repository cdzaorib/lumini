# Evidências T08b — API e painel de agenda/reservas

Data: 2026-10-05. Somente ambiente local e dados sintéticos. Nenhum fornecedor externo chamado; Google Calendar substituído por calendário em memória.

## Backend

- `ruff check`, `ruff format --check`, `mypy` strict (47 arquivos): verdes.
- **152 unitários** (+22: schemas de agenda e ações; preflight CORS `PUT`) e **119 integrações** contra PostgreSQL 15.19 / Redis 7.0.15 locais (`lumini_foundation_test`), com `-W error`, zero skips/warnings, repetidas 3 vezes sem instabilidade.
- Integrações novas (`tests/integration/test_booking_admin_api.py`, 27 casos): anônimo recebe 401 antes de abrir sessão de banco ou tocar no calendário (9 rotas); agenda versionada sem tocar em credenciais e com auditoria só de IDs; agenda inválida (sobreposição, fora da grade, início ≥ fim, dia inválido, fuso, markup, campo extra) → 422 sem eco; troca de calendário bloqueada enquanto há reserva ativa e também enquanto a remoção do evento está pendente; prévia igual ao cálculo da reserva; recusas `evaluation_required`, `calendar_unavailable` (sem texto do fornecedor) e `calendar_not_configured`; contato visível na lista da equipe; sinal com valor divergente, versão velha, estado errado e prazo vencido recusados; ator `staff` + `sub` registrado; histórico × próximas (confirmada realizada sai da fila; reserva aguardando sinal continua); conflito liberado uma vez; reagendamento pela equipe devolve a nova reserva, é idempotente e recusa horário a menos de 3h e reserva não confirmada; 404 com código.
- **Defeito corrigido no núcleo (T08a)** e coberto por regressão `test_a_long_lived_session_never_acts_on_an_old_copy`: leituras sem trava usavam a cópia da reserva já carregada na sessão. Controle negativo: removendo a correção, o worker enviou `hold_created` para uma reserva cancelada; com a correção, só `booking_cancelled` e o evento é removido.
- Migrações inalteradas (`0003_bookings`); `alembic upgrade head` + `alembic check` sem drift em banco recriado. Tabelas vazias e nenhuma trava advisory ao final das suítes.

## Painel `/admin` de ponta a ponta (navegador real)

Montagem fora do repositório (scratchpad, descartada): banco `lumini_e2e_test` migrado e semeado (profissional verificada, procedimento publicado de agendamento direto, 4 reservas: duas aguardando sinal, uma em conflito, uma confirmada), backend real `create_app` em `127.0.0.1:8100` com verificador de identidade sintético e `FakeCalendar`, `next dev` em `127.0.0.1:3100`, Google Chrome 151 via `playwright-core` 1.63 com stub do script do Google, navegador no fuso de Lisboa.

Roteiro **26/26**: login abre Reservas → grupos (decisão 1, aguardando sinal 2, confirmadas 1) → contato, prazo do sinal e horário em Brasília (10:00–11:00 mesmo com navegador em outro fuso) → valor divergente recusado com mensagem → valor exato + conferência confirmam e a reserva passa a "Atualizando o Google Agenda" (foco preservado) → conflito explicado e liberado → cancelamento → reagendamento escolhendo horário da prévia → histórico com motivos → Agenda carregada (calendário e 7 faixas) → sobreposição barrada no navegador → salvar e recarregar com a alteração → troca de calendário recusada com reservas ativas → prévia de 7 dias → 390px sem rolagem horizontal nas duas abas → sair limpa a sessão (sem storage/cookie, `disableAutoSelect`). **Violações de CSP: 0. Erros de console: 0**, além dos dois 409 das recusas intencionais (o Chrome registra respostas 409 como falha de recurso).

Defeito encontrado e corrigido pelo E2E: ao trocar para Histórico, o título mudava antes da lista chegar. Agora título e lista mudam juntos.

## Build de produção

`npm run lint`, `npm run typecheck` e `npm run build` verdes (`/admin` dinâmica, proxy incluído). Prévia religada em `127.0.0.1:3000` sem variáveis do painel: “Painel não configurado”, CSP com nonce, `no-store`.

## Não validado

Google Calendar real (adaptador é T08c), worker agendado (as reservas ficam em `pending_calendar`/`confirming` até o worker existir), login Google real, envio de mensagens, HTTPS/deploy, suíte E2E versionada.
