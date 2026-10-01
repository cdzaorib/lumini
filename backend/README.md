# Backend Lumini — fundação

Python 3.12+, FastAPI, SQLAlchemy/Alembic, PostgreSQL, Celery/Redis. Sem dados da clínica e sem credenciais. O worker compartilha `src/lumini` com a API.

## Desenvolvimento

Na pasta `backend/` (a raiz possui um uv local em `.tools/bin/uv`):

```bash
../.tools/bin/uv sync --frozen --python 3.12
../.tools/bin/uv run uvicorn lumini.app:create_app --factory --host 127.0.0.1 --port 8000
```

VS Code (IDE escolhida): selecionar o interpretador `backend/.venv/bin/python`. Execução: módulo `uvicorn`, argumentos `lumini.app:create_app --factory --host 127.0.0.1 --port 8000`, diretório de trabalho `backend/`. O interpretador do sistema 3.11 não atende este projeto; uv gerencia o 3.12 isoladamente.

`GET /health/live` verifica o processo. `GET /health/ready` faz `SELECT 1` no PostgreSQL e `PING` no Redis e retorna 503 se faltar configuração ou conexão. Readiness verifica **conectividade apenas**; não atesta schema atualizado, autenticação, agenda, modelos ou WhatsApp. `/docs` e `/openapi.json` só existem fora de produção.

Rotas de catálogo (contrato completo em `../docs/API-ADMIN.md`): `/api/admin/*` exige Google ID token válido + allowlist em **toda** rota, verificado antes de abrir sessão de banco; `GET /api/catalog/services` é público e lista somente serviços publicados cujas aprovações, credenciais e conteúdo continuam válidos.

## Configuração

Somente variáveis de processo com prefixo `LUMINI_`; não há carregamento implícito de `.env`, `DATABASE_URL` ou dados de outro projeto.

| Variável | Uso / padrão |
|---|---|
| `LUMINI_ENVIRONMENT` | `development`, `test` ou `production`; padrão `development` |
| `LUMINI_DATABASE_URL` | URL PostgreSQL; aceita `postgres://`, `postgresql://`, `postgresql+asyncpg://`; opcional para a API iniciar |
| `LUMINI_REDIS_URL` | URL `redis://` ou `rediss://`; opcional na API, obrigatória no worker |
| `LUMINI_CORS_ORIGINS` | JSON de origens explícitas, ex.: `["http://localhost:3000"]`; padrão lista vazia |
| `LUMINI_DEPENDENCY_TIMEOUT_SECONDS` | Prazo por dependência; padrão 2 segundos |
| `LUMINI_GOOGLE_CLIENT_ID` | Client ID OAuth (identificador público, não segredo); sem ele `/api/admin/*` responde 503 |
| `LUMINI_ADMIN_EMAILS` | JSON de e-mails autorizados; vazio = acesso administrativo bloqueado |
| `LUMINI_REVIEWER_ASSIGNMENTS` | JSON e-mail → lista de UUIDs de profissionais que aquela identidade pode aprovar; e-mails precisam estar na allowlist |

Credenciais devem vir de ambiente seguro/gerenciador de segredos. Não colar URLs reais em comandos registrados no histórico. Configurações escondem segredos em `repr`/JSON; nunca serialize o resultado bruto de `ValidationError.errors()`, pois Pydantic pode incluir os valores de entrada nessa estrutura.

Falhas de construção dos clientes Redis/SQLAlchemy e do engine de migração são exibidas com mensagens fixas, sem a cadeia de exceções dos drivers (que pode conter valores sensíveis da querystring). URLs Redis não podem definir `ssl_cert_reqs` ou `ssl_check_hostname`: essas opções ficam sob controle da aplicação.

## Migrações

```bash
# Gera SQL sem banco nem credencial; não prova execução no PostgreSQL.
../.tools/bin/uv run alembic upgrade head --sql
# Somente após configurar uma instância local/de teste:
../.tools/bin/uv run alembic upgrade head
```

`0001_catalog` cria catálogo vazio (profissionais, serviços e vínculo). `0002_catalog_workflow` adiciona revisões, aprovações por profissional/revisão e auditoria mínima (ator `sub`, alvo UUID, ação, revisão), sem copiar texto clínico nem e-mails. Regras de fluxo vivem em `lumini.catalog.service`. Nenhum conteúdo/conta é semeado. Modelos não são criados automaticamente ao iniciar a API.

## Worker

```bash
../.tools/bin/uv run python -m lumini.worker
```

Celery está configurado para mensagens JSON, UTC, sem resultados/eventos de tarefas, e requer Redis explicitamente. Não há tarefas de negócio registradas nem confirmação simulada de pagamento/agenda. Jobs futuros devem transportar IDs mínimos, ser idempotentes e consultar prazos persistidos no PostgreSQL. Expirações de duas horas não dependerão de uma tarefa ETA em memória nem de TTL Redis isolado.

Para `rediss://`, o broker exige certificado válido (`CERT_REQUIRED`) e validação do hostname. O teste inspeciona as opções efetivamente resolvidas pelo Kombu; handshake TLS contra um provedor remoto ainda não foi validado.

## Verificação

```bash
../.tools/bin/uv run ruff check .
../.tools/bin/uv run ruff format --check .
../.tools/bin/uv run mypy
../.tools/bin/uv run pytest
```

Por padrão são executados os testes unitários com probes sintéticos; o marker `integration` é **deselecionado**, sem skips implícitos. Não há SQLite, mocks apresentados como integrações nem fixture com dados da clínica.

### Integração opt-in

Com instâncias isoladas de PostgreSQL/Redis e migração já aplicada, fornecer no ambiente de processo `LUMINI_INTEGRATION_DATABASE_URL` e `LUMINI_INTEGRATION_REDIS_URL`, então executar:

```bash
../.tools/bin/uv run pytest -m integration
```

O nome do banco precisa terminar em `_test`, validado antes de qualquer conexão de escrita. A suíte falha explicitamente se as variáveis faltarem ou o nome for inseguro; não recorre às URLs normais da aplicação. Toda inserção sintética fica dentro de transação revertida ao finalizar, inclusive em falhas. Não há limpeza de tabelas, `FLUSHALL`, criação/remoção de banco nem commit de dados. Redis recebe somente PING. Os testes exercitam constraints do catálogo, chaves estrangeiras, defaults e readiness real da API com as duas dependências. Eles não validam Railway, Google, Evolution, modelos ou um worker Celery consumindo tarefas.

## Documentação técnica consultada

- [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [SQLAlchemy asyncio](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Celery configuration](https://docs.celeryq.dev/en/stable/userguide/configuration.html)
