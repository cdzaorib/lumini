# Evidências T08d — autoatendimento por link seguro

Data: 2026-10-05. Somente ambiente local e dados sintéticos. Calendário em memória; nenhum fornecedor externo chamado.

## Backend

- `ruff`, `ruff format --check`, `mypy` strict (58 arquivos): verdes.
- **211 unitários** (+17: token, adulterações, expiração, rotação de segredo, URL, validação de `LUMINI_PUBLIC_SITE_URL` e do tamanho do segredo) e **140 integrações** (+13) com `-W error`, **20 rodadas seguidas verdes**; Redis sem chaves `lumini:*` ao final.
- Integração da API pública (`test_self_service_api.py`): link vazio/malformado/de outra chave/expirado/adulterado → mesmo 404 antes de abrir sessão de banco e sem tocar no calendário (4 rotas); reserva inexistente igual a link inválido; sem segredo → 503; visão da cliente sem nome, telefone ou id interno; reserva aguardando sinal pode ser devolvida mas não reagendada (`not_confirmed`), cancelamento registrado como `client`; com exatamente 24 h tudo vai para a clínica (`within_24h`); um reagendamento mantém o sinal, devolve link novo, o antigo mostra a original cancelada, e o segundo é recusado (`second_reschedule`); limite de consultas de horário por link (429); equipe gera link só para reservas abertas, com auditoria, e 503 quando não configurado.
- **Defeito da T08a corrigido**: com 8 reservas simultâneas no mesmo horário, o PostgreSQL às vezes abortava uma por deadlock na restrição de exclusão (falha em ~1 a cada 7 rodadas da suíte; a integridade nunca foi violada). Agora a transação é repetida; regressão determinística (deadlock simulado na 1ª tentativa; desiste após 3) e 20 rodadas completas sem falha.

## Navegador (Chrome 151, `playwright-core`, scratchpad descartado)

Backend real com segredo sintético do link e calendário em memória, `next dev` na porta 3100, navegador no fuso de Tóquio.

- Cliente **18/18**: painel gera link `/reserva#<token>` → resumo da reserva confirmada em horário de Brasília (“Quarta-feira, 7 de outubro, das 10:00 às 11:00”) sem dados de contato → horários livres → reagendamento → link trocado para a nova reserva, sem novo reagendamento nem cancelamento online → recarregar mantém a nova → link antigo mostra a original cancelada → reserva aguardando sinal mostra prazo e valor e é cancelada (foco volta ao título) → fragmento malformado explicado sem chamar a API → token só no cabeçalho `Authorization`, nunca na URL da API (9 chamadas) → 390 px sem rolagem horizontal → CSP 0 violações, console 0 erros.
- Painel **26/26** (roteiro da T08b repetido, sem regressão).
- Defeitos encontrados e corrigidos: abrir outro link na mesma aba (só muda o fragmento) mantinha a reserva anterior; `capitalize` deixava “Quarta-Feira, 7 De Outubro”.

## Build

`npm run lint`, `typecheck` e `build` verdes (`/reserva` dinâmica). Prévia religada em `127.0.0.1:3000` sem variáveis: `/reserva` responde com `Referrer-Policy: no-referrer`, `X-Robots-Tag: noindex, nofollow`, `no-store`.

## Não validado

Envio automático do link pelo WhatsApp (T09), domínio/HTTPS reais, comportamento de pré-visualização de link no WhatsApp (o fragmento não é enviado, então a pré-visualização é genérica).
