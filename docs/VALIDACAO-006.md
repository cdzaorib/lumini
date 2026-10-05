# Evidências T09 — WhatsApp (Evolution), modo humano e avisos

Data: 2026-10-05. Somente ambiente local e dados sintéticos. **Nenhuma instância Evolution nem número de WhatsApp foi usado**: remetente falso e webhooks simulados com o formato documentado.

## Backend

- `ruff`, `ruff format --check`, `mypy` strict (69 arquivos): verdes. Migração `0004_whatsapp`: upgrade → downgrade → upgrade e `alembic check` sem divergência.
- **238 unitários** (+27: leitura de payload — grupos, status, canais, `@lid`, mídia, horários; escolha numérica; formatação em reais; variantes do nono dígito; cliente Evolution com sucesso, sem redirect, recusas e quedas sem texto do provedor; configuração) e **161 integrações** (+21) com `-W error`, **10 rodadas seguidas verdes**, banco limpo ao final.
- Integração (`test_whatsapp.py`): webhook sem token/token errado/outra instância/corpo grande/JSON inválido/sem configuração recusados **antes de qualquer acesso ao banco**; menu respondido uma vez e reentrega ignorada; texto da cliente não fica guardado; eco do próprio envio mantém o bot; **eco chegando antes da resposta do envio** reconhecido; equipe digitando durante um envio pausa o bot assim que o envio termina; resposta da equipe pausa o bot, `#bot` da cliente não reativa, `#bot` da clínica reativa; `#pausa`; `fromMe` indefinido bloqueia envios e vira equipe após a carência; **reserva completa pelo WhatsApp** até `create_hold` (contato com telefone do chat, nome fora do estado depois) e avisos “reserva criada” e “sinal” enviados; menções de saúde e “sim” na pergunta de saúde vão para a equipe sem perguntas; atendente e STOP; mídia e histórico antigo; avisos suspensos em modo humano com nota no outbox, link de autoatendimento enviado uma vez, `human_handoff` pausa o bot; resposta perdida em queda reenviada só se ainda atual; número recusado não é reenviado; estado da conexão e conversas com a equipe no painel; logs sem telefone nem texto; worker responde o que o caminho rápido perdeu.

## Navegador (Chrome 151, `playwright-core`, scratchpad descartado)

- Integrações **12/12**: webhook sem token 401 → queda registrada → aviso no topo do painel → aba com estado, instruções de QR Code, `#bot`/`#pausa` e 1 conversa com a equipe → reconexão some com o aviso e `#bot` zera a contagem → 390 px sem rolagem → CSP 0, console 0.
- Painel **26/26** e cliente **18/18** repetidos sem regressão.

## Build

`npm run lint`, `typecheck`, `build` verdes; prévia religada em `127.0.0.1:3000`.

## Não validado (bloqueia lançamento)

PoC com instância de teste (`RUNBOOK-WHATSAPP.md`): cabeçalho customizado do webhook na versão usada, igualdade entre id do envio e do eco, resposta pelo celular e pelo WhatsApp Web, nono dígito, `@lid`, queda/reconexão real, reentrega. Aprovação dos textos pela clínica. Decisão da clínica sobre lembretes em modo humano.
