# Lumini

Landing page e assistente de atendimento/agendamento. Frontend Next.js e backend Python/FastAPI. O projeto está na **fundação local**, não disponível para clientes.

## Retomada

Comece por [docs/HANDOFF.md](docs/HANDOFF.md). Escopo aprovado em [docs/PLANO.md](docs/PLANO.md), decisões em [docs/DECISOES.md](docs/DECISOES.md), evidências por tarefa em [docs/TAREFAS.md](docs/TAREFAS.md). Claude lê [CLAUDE.md](CLAUDE.md); regras de todos os agentes em [AGENTS.md](AGENTS.md).

## Estrutura

```text
backend/          FastAPI, modelos, migrações, worker e testes Python
frontend/         Next.js, TypeScript e Tailwind
infrastructure/   notas de implantação futura
docs/             plano, decisões, tarefas e handoff vivo
```

O worker compartilha o pacote `backend/src/lumini`. Ele será processo separado na hospedagem, não um segundo código duplicado.

## Desenvolvimento

Requer Node 22.23.2 compatível e uv. Nesta máquina o Node padrão é 18; consulte [docs/AMBIENTE.md](docs/AMBIENTE.md) para ativar Node 22. uv local em `.tools/bin/uv`, com Python 3.12 isolado no backend.

```bash
make install
make check
make api
# outro terminal:
make web
```

API em `http://127.0.0.1:8000`, frontend em `http://127.0.0.1:3000` (somente local). Sem variáveis de conexão, liveness responde 200 e readiness 503. Isso é esperado: a API inicia, mas não afirma que PostgreSQL/Redis estejam disponíveis. No PyCharm selecione `backend/.venv/bin/python`.

## Integrações

| Componente | Estado inicial |
|---|---|
| API, frontend e testes locais | Executáveis e verificados; ver handoff e relatórios |
| PostgreSQL/Redis | Testados em instâncias locais efêmeras; Railway não configurado |
| Celery | Worker conectado ao Redis local e respondendo; sem jobs de negócio |
| Calendar, Evolution, IA e login Google | Não integrados |
| CI | Workflow preparado; execução remota não realizada |
| Railway/Vercel/domínio | Não provisionados |

Não há agendamento, confirmação de sinal, chat nem painel operacional nesta fundação. A página é prévia interna, com indexação desativada. Não publicar como produto pronto.

## Continuidade por tarefa

Ao encerrar cada tarefa: atualizar `docs/TAREFAS.md`, `docs/HANDOFF.md` e decisões alteradas. Informar os checks realmente executados e distinguir integração real, mock e preparação. Nunca incluir dados de clientes, chaves ou URLs de sessão remota no Git.
