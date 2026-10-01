# Evidências T07/T07b — autenticação administrativa, catálogo e painel

Data: 2026-10-01. Somente ambiente local e dados sintéticos. Nenhum fornecedor externo foi chamado com credencial; nenhuma conta Google da clínica existe ainda.

## Backend

- `ruff check`, `ruff format --check`, `mypy` (strict, 28 arquivos): verdes.
- **121 unitários** (inclui 47 de autenticação com tokens RS256 assinados por chaves sintéticas geradas no teste) e **55 integrações** contra PostgreSQL 15.19 / Redis 7.0.15 locais (`lumini_foundation_test`), com `-W error`: zero warnings/skips.
- Migração `0002_catalog_workflow`: upgrade → downgrade → upgrade e `alembic check` sem drift.
- Após as suítes: tabelas do catálogo vazias e nenhuma trava advisory remanescente.

## Painel `/admin` de ponta a ponta (navegador real)

Montagem, toda fora do repositório (scratchpad da sessão, descartada):

- Banco separado `lumini_e2e_test` (migrado com Alembic, removido ao final) com uma profissional sintética semeada.
- Backend real `create_app(...)` em `127.0.0.1:8100` com `LUMINI_*` sintéticos e `app.state.identity_verifier` substituído por um verificador que aceita apenas tokens assinados por uma chave RSA gerada na hora. Smoke: admin 200, e-mail fora da allowlist 403, anônimo 401.
- Frontend `next dev` em `127.0.0.1:3100` com `NEXT_PUBLIC_GOOGLE_CLIENT_ID` fictício e `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8100`.
- Google Chrome 151 via `playwright-core` 1.63 (instalado só no scratchpad). `https://accounts.google.com/gsi/client` foi respondido com stub cujo botão entrega o token sintético.

Roteiro aprovado (12/12 etapas): tela de login → login e carga do catálogo → verificação de credencial bloqueada sem a confirmação e registrada com ela (foco volta ao título do card) → cadastro de profissional → erro local para valor monetário inválido → procedimento salvo como rascunho → aprovação pela profissional atribuída → publicação; o catálogo público passou a listá-lo com `council_registration` e **sem** restrições de comunicação nem dados do revisor → edição criou a revisão 2, despublicou e o retirou do catálogo público → 390px sem rolagem horizontal → teclado alcança “Sair” → sair limpa a sessão, chama `disableAutoSelect` e nenhum token fica em localStorage, sessionStorage ou cookie. **Violações de CSP: 0; erros de console: 0.**

Script **real** do Google (sem stub) sob a mesma CSP: carregou, criou o iframe do botão, **0 violações de CSP**. Erros de console esperados para Client ID fictício (“client ID is not found”, 403) e 404 de `favicon.ico`.

Capturas inspecionadas em 1280px e 390px; o link “Pular para o conteúdo” fica oculto em repouso, aparece com Tab e leva o foco a `#conteudo` (o aparecimento no meio das capturas de página inteira era artefato da captura).

## Build de produção

- `npm run lint` e `npm run typecheck` verdes; `npm run build` verde: `/` estática, `/admin` dinâmica, proxy incluído.
- Prévia religada em `127.0.0.1:3000` com o build novo e **sem** variáveis do painel: `/admin` mostra “Painel não configurado”, não carrega o script do Google, envia CSP com nonce diferente a cada requisição, sem `'unsafe-eval'`, com `Cache-Control: no-store`; scripts com nonce e hidratação sem violações no Chrome. `/` inalterada.

## Não validado

Login Google real (Client ID e e-mails da clínica), HTTPS/domínio, Vercel/Railway, CSP da landing, suíte E2E versionada no repositório/CI (os scripts desta validação ficaram fora do Git).
