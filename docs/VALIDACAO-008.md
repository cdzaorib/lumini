# Evidências T11 — itens restantes do plano que dependem só de código

Data: 2026-10-05. Somente ambiente local e dados sintéticos; nenhum serviço externo chamado.

## Entregas

- **T11a** conteúdo do site e instruções do sinal no painel (migração 0006), regra de publicidade, API pública sem dados privados, bot com instruções reais do sinal.
- **T11b** comparecimento (migração 0007), histórico da reserva, métricas do plano §11, origem da reserva; `booking_events` com `clock_timestamp()`.
- **T11c** aviso de compromisso de terceiros sobre reserva ativa (migração 0008), sem alterar a reserva.
- **T11d** cenários de navegador versionados em `e2e/` e `make e2e`.
- **T11e** revisão de acessibilidade/interface e de segurança (`SEGURANCA.md`, teste de rotas).

## Backend

`ruff`, `ruff format --check`, `mypy` strict (96 arquivos): verdes. Migrações 0006–0008 com ida e volta e `alembic check` sem divergência. **299 unitários** e **189 integrações** com `-W error`, 3 rodadas verdes. Teste de rotas: todas as rotas `/api/admin` respondem 401 sem login (chamadas a partir do OpenAPI) e a superfície pública é exatamente a lista revisada.

## Navegador (`make e2e`, Chrome 151)

Os 7 cenários aprovados, antes e depois da revisão de interface: painel 26/26, autoatendimento 18/18, integrações 12/12, site e contato 17/17, chat 16/16, resumo/comparecimento/histórico 10/10, conteúdo do site 12/12 (111 etapas), CSP 0 e console 0 em todos.

## Revisão de interface (Vercel Web Interface Guidelines)

Achados corrigidos:

- `frontend/src/app/_site/lead-form.tsx:75` placeholder sem “…”; `:9` `select` sem cor de texto explícita
- `frontend/src/app/_site/chat.tsx:156` placeholder sem “…” e campo sem `name`; `:159` botão de enviar desabilitado antes do envio; `:114` rolagem do histórico vazando (`overscroll-contain`); `:120` mensagens longas sem quebra
- `frontend/src/app/_site/chat-widget.tsx:26` diálogo sem `overscroll-behavior: contain`
- `frontend/src/app/_site/chrome.tsx:17` marca sem `translate="no"`; links do rodapé sem estado de hover; títulos de seção sem `text-balance`
- `frontend/src/app/page.tsx:86` título sem `text-balance`; `:58` nome de procedimento longo sem quebra; links sem hover
- `frontend/src/app/procedimentos/[slug]/page.tsx:48` e `frontend/src/app/atendimento/page.tsx:26` títulos sem `text-balance`
- `frontend/src/app/reserva/self-service.tsx:295` campo de data sem `name`/`autocomplete`; marca sem `translate="no"`
- `frontend/src/app/globals.css` sem `touch-action: manipulation` e cor de toque definida

Não aplicáveis: “Title Case” (português usa só a inicial maiúscula) e estado das abas na URL (painel interno). Pendente: revisão com leitor de tela e medição de desempenho em produção.

## Não validado

O mesmo de `VALIDACAO-007.md` (provedores reais, deploy) e a reconciliação de sobreposição no navegador (roda no worker).
