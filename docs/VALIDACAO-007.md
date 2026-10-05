# Evidências T10 — IA, experiência pública e piloto

Data: 2026-10-05. Somente ambiente local e dados sintéticos. **Nenhum provedor de IA, Google, Evolution ou hospedagem foi chamado com credencial.**

## Backend

- `ruff`, `ruff format --check`, `mypy` strict (86 arquivos): verdes. Migração `0005_leads_ai`: upgrade → downgrade → upgrade e `alembic check` sem divergência.
- **285 unitários** e **180 integrações** com `-W error`, 3 rodadas verdes, banco limpo ao final.
- IA (T10a): redação de identificadores (telefones, e-mail, documento, CEP, links, perfis, números longos); guardrails (promessa, “sem dor”, adequação individual, número fora dos fatos, tamanho); cliente com JSON determinístico, sem redirect e falhas como fallback; classificador aceita só procedimentos do catálogo; texto não redigido nunca sai; redator só com fatos aprovados e restrições; IA desligada sem `LUMINI_AI_ENABLED`; bancada sintética com provedor-oráculo: saúde decidida localmente (0 casos chegam ao modelo), 0 vazamentos após redação. No canal: rota por confiança (alta/média/baixa), modelo nunca consultado em nome/confirmação, contabilidade `ai_calls` sem texto.
- Leads (T10b): telefone brasileiro, consentimento obrigatório, sem texto livre, armadilha de robô, deduplicação diária, limite por endereço, painel, exclusão após 90 dias (convertidos mantidos).
- Chat web (T10d): token fora do banco (só hash), recusa antes do banco, sessão expira em 24 h e é apagada, reserva completa com passo de WhatsApp, saúde/equipe encaminhadas ao formulário, nada do texto gravado, limite por sessão.

## Navegador (Chrome 151, `playwright-core`, scratchpad descartado)

- Site **17/17**: CSP por nonce e `noindex`; procedimento publicado com preço pela regra; profissional com registro; pendências só como aviso de prévia; políticas; nada inventado; página do procedimento; formulário só envia com consentimento e sem campo livre; privacidade como rascunho; pedido na aba Contatos com link de WhatsApp; status filtrável; 390 px; 404 amigável; CSP 0, console 0 (exceto o 404 intencional).
- Chat **16/16**: menu e respostas rápidas, procedimentos, pergunta de saúde, dias em horário de Brasília com navegador em Nova York, nome, WhatsApp com aviso, resumo com sinal, reserva visível para a equipe, saúde encaminhada, token só em cabeçalho, widget na landing, 390 px, CSP 0, console 0 (após incluir ícone do site).
- Regressão: painel 26/26, cliente 18/18, integrações 12/12.

## Backup e restauração (T10e)

`infrastructure/backup/backup.sh` + `restore.sh` com PostgreSQL 15.19 local sobre o banco E2E populado: 17 tabelas com contagens idênticas, `alembic_version` 0005 nos dois, dump 600 em pasta 700; recusas: destino com tabelas (saída 3), destino igual à origem (saída 2), arquivo adulterado (checksum). Bancos temporários removidos.

## Build

`npm run lint`, `typecheck`, `build` verdes; prévia religada em `127.0.0.1:3000` (sem API configurada: site no ar, lista e formulário indisponíveis com mensagem).

## Não validado

Provedor de IA real e benchmark real; Jev; Google, Evolution e login Google reais; domínio/HTTPS/deploy; backup automático do provedor; leitor de tela; desempenho em produção; aprovação jurídica e da clínica. Estado completo em `LANCAMENTO.md`.
