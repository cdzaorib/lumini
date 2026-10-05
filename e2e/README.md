# Cenários de navegador (E2E)

Roteiros no Chrome contra o backend real e o `next dev`, com **dados sintéticos** e identidade, Google Agenda e WhatsApp simulados. Cada cenário recebe um banco novo (`lumini_e2e_test`, recriado e migrado por `server.py`, que recusa servidores não locais).

```bash
cd e2e && npm ci
LUMINI_E2E_ADMIN_DATABASE_URL=postgresql://lumini_test@127.0.0.1:55432/postgres \
LUMINI_E2E_REDIS_URL=redis://127.0.0.1:56379/1 \
node run.mjs            # todos
node run.mjs chat site  # só os que contêm esses nomes
```

Variáveis opcionais: `E2E_CHROME` (padrão `/usr/bin/google-chrome`), `E2E_SITE` (`http://127.0.0.1:3100`), `E2E_API` (`http://127.0.0.1:8100`), `E2E_OUTPUT` (capturas em `e2e/.output/`, fora do Git). As portas 3100 e 8100 precisam estar livres. `make e2e` faz o mesmo a partir da raiz.

Cenários: painel de reservas e agenda, autoatendimento da cliente, integrações e WhatsApp, site e pedidos de contato, chat, resumo/comparecimento/histórico e conteúdo do site (este por último, porque o conteúdo público fica 60 s em cache). Cada um termina com “N/N etapas aprovadas”; o resumo final lista PASS/FAIL e o código de saída é 1 se algo falhar.
