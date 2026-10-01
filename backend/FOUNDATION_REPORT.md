# T02 — Fundação backend

Concluída localmente em 2026-10-01, com complemento de integração T04 abaixo. Proprietário da edição: agente `backend_foundation`; somente caminhos dentro de `backend/`. Nenhum commit, deploy, fornecedor remoto ou dado da clínica.

## Entregue

- Pacote `src/lumini` Python >=3.12, ambiente uv isolado e `uv.lock`.
- App factory FastAPI com lifespan: clientes são criados sem conectar e fechados ao encerrar.
- Configuração exclusivamente via ambiente `LUMINI_`, URLs protegidas por `SecretStr`, erros públicos de readiness limitados a estados fixos.
- `GET /health/live`: processo vivo. `GET /health/ready`: consulta PostgreSQL e Redis, 503 quando não configurados/indisponíveis. Readiness não confirma schema ou fornecedores.
- CORS por origens explícitas, somente GET na fundação; docs/OpenAPI desligados em produção; sem endpoints de administração, agenda ou pagamento.
- SQLAlchemy assíncrono e fábrica de sessões; Alembic `0001_catalog` cria catálogo vazio com profissionais, serviços e relação, valores/durações restritos e metadados de aprovação.
- Celery no mesmo pacote; broker explicitamente configurado, serialização JSON, UTC, sem resultados/eventos ou tarefas fictícias.
- README com configuração PyCharm, comandos, variáveis e limites.
- Sem interfaces prematuras de LLM com prompt livre: contratos de contexto aprovado/allowlist serão implementados na fase de provedores conforme ADR-007.

## Evidência executada

Na pasta `backend/`, usando `../.tools/bin/uv`:

| Comando | Resultado |
|---|---|
| `uv sync --python 3.12` | Ambiente instalado; Python 3.12.14 (sistema é 3.11.2) |
| `uv lock --check` | Lock consistente, 54 pacotes resolvidos |
| `uv run ruff check .` | Verde |
| `uv run ruff format --check .` | 21 arquivos formatados (após revisão final) |
| `uv run mypy` | Verde, 19 arquivos de código (após revisão final) |
| `uv run pytest` | **30 passed, 14 deselected**, sem warnings (integração opt-in) |
| `uv run pytest -m integration` | **14 passed, 30 deselected** em PostgreSQL/Redis locais reais |
| `uv run alembic upgrade head --sql` | SQL PostgreSQL gerado com sucesso, sem conectar banco |
| `uv run alembic heads` | `0001_catalog (head)` |

Cobertura significativa: segredos mascarados, configuração inválida sem eco, isolamento de `.env`/variáveis de outro projeto, liveness independente, readiness ausente/falha/sucesso sintético, erro inesperado sem vazamento, timeout, CORS, docs em produção, ausência de mutação, limpeza de conexões e worker sem broker/tarefas fictícias.

Versões resolvidas: FastAPI 0.142.2, SQLAlchemy 2.0.54, Alembic 1.20.0, Celery 5.6.3, Redis client 6.4.0, Pydantic 2.13.5. Starlette 1.7 usa `httpx2` no TestClient; a dependência de teste é `httpx2==2.13.1` (fonte PyPI aponta para o projeto pydantic/httpx2), evitando o aviso de depreciação do antigo httpx.

## Estado real e limitações

- **Real local:** pacote instalável, factory e endpoints através de TestClient, lockfile, checks, geração SQL e integração com PostgreSQL/Redis temporários em T04 (detalhes abaixo).
- **Mock:** probes nos testes unitários de readiness e fixtures de lifecycle. Esses testes unitários continuam distintos da suíte de integração real.
- **Apenas preparado:** worker Celery; migração em ambiente remoto.
- **Não iniciado:** autenticação Google, autorização administrativa, workflow completo de aprovação, API de catálogo, reservas/agenda, outbox, WhatsApp/PoC Evolution, provedores IA e chat.
- Não usei SQLite. T04 validou conexões e constraints em PostgreSQL/Redis reais locais. O coordenador aplicou a migração e executou `alembic check` antes da suíte. Consumo de fila Celery, execução de CI remota e Railway continuam não validados.
- As constraints iniciais exigem metadados para aprovação/publicação; a política de credenciais, autoria autenticada e invalidar aprovação após mudanças ainda depende do serviço de domínio futuro. Nenhuma escrita administrativa está exposta.
- Segurança do worker com payloads reais ainda exige implementação de jobs ID-only e controle de logs; nenhum dado sensível deve ser serializado em fila.
- `.venv` é local/ignorada; nenhum segredo foi carregado ou copiado. A configuração não registra DSNs, mas consumidores nunca devem registrar `ValidationError.errors()` bruto.

## Próximo passo executável

Reproduzir em CI os checks e a suíte de integração, com PostgreSQL/Redis efêmeros e banco de sufixo `_test`. Depois implementar autenticação/autorizações e catálogo/aprovação antes das mutações de agenda. O coordenador atualizará `docs/TAREFAS.md` e `docs/HANDOFF.md` com esta evidência.

## Complemento T04 — integração real local (2026-10-01)

O coordenador iniciou instâncias temporárias isoladas: PostgreSQL 15.19 em loopback porta 55432, banco `lumini_foundation_test`, e Redis 7.0.15 em loopback porta 56379. Não são serviços de produção/Railway. A suíte usou somente essas instâncias sintéticas, pelas variáveis `LUMINI_INTEGRATION_DATABASE_URL` e `LUMINI_INTEGRATION_REDIS_URL`.

Arquivos adicionados: `tests/integration/conftest.py`, `test_postgres.py`, `test_readiness.py`, e marcadores de pacote de testes. `pyproject.toml` registra marker `integration` e exclui-o por padrão; não há skips silenciosos. `tests/conftest.py` preserva apenas as duas URLs explicitamente destinadas à integração, removendo as configurações normais da aplicação durante os testes.

A fixture valida nome de banco terminado em `_test` **antes de conectar para escrita**. Cada teste de catálogo usa transação externa revertida, e violations esperadas usam savepoints. Validados no PostgreSQL real: estado inicial draft; intervalo de 15 minutos; JSON vazio; valores de preço/sinal não inventados; timestamp com timezone; vínculo válido; ambas as FKs; estados inválidos; modo inválido; duração/intervalo/valores inválidos; metadados de aprovação/publicação obrigatórios. A readiness real efetuou SELECT 1 e PING, retornando 200 com ambas as dependências `ok`, sem override de probe.

Resultado final: **14 testes de integração aprovados**, **24 unitários aprovados**, Ruff/format/mypy/lockfile verdes. Consulta somente leitura após a suíte confirmou `professionals=0`, `services=0`, `professional_services=0`: nenhum registro persistido. Não executou FLUSHALL, limpeza de tabelas, drop database ou commit de fixtures. Um caso de teste inicialmente violava simultaneamente dois checks; foi ajustado para isolar o check de status, sem mudar o schema.

A posse/processos das instâncias temporárias permanece com o coordenador, que realizará a própria validação de downgrade/reupgrade e encerramento. Esta tarefa não iniciou nem encerrou serviços.

## Correções da revisão independente final (2026-10-01)

A revisão detectou que o Kombu usava `CERT_NONE` por padrão com `rediss://` e que parâmetros inválidos na querystring podiam aparecer em exceções durante a criação de clientes, antes da readiness.

- `create_worker` agora impõe `CERT_REQUIRED` e validação de hostname no broker TLS. O teste verifica o objeto real retornado por `connection_for_write().ssl`, sem abrir conexão. `Settings` rejeita `ssl_cert_reqs` e `ssl_check_hostname` na querystring, pois o transporte pode dar prioridade à URL e enfraquecer a política.
- Construção dos clientes Redis/SQLAlchemy e criação do engine Alembic estão dentro de tratamento com mensagem fixa e `raise ... from None`; cleanup do engine continua garantido quando Redis falha.
- Regressões reproduzem valores sensíveis sintéticos em `socket_timeout` Redis e `async_fallback` PostgreSQL, verificando que o traceback exibido não contém esses valores. O cenário Alembic também está coberto.
- Validação final: **30 unitários + 14 integrações reais locais aprovados**, Ruff/format/mypy/lockfile verdes e geração SQL Alembic preservada. **Configuração TLS validada; handshake TLS remoto não testado.**
