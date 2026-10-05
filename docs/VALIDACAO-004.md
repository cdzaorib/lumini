# Evidências T08c — worker periódico, adaptador Google Calendar e reconciliação

Data: 2026-10-05. Somente ambiente local e dados sintéticos. **Nenhuma chamada ao Google**: não existe conta de serviço da clínica; as respostas do Google foram simuladas.

## Backend

- `ruff check`, `ruff format --check`, `mypy` strict (53 arquivos): verdes.
- **194 unitários** (+42) e **127 integrações** (+8) contra PostgreSQL 15.19 / Redis 7.0.15 locais, `-W error`, zero skips/warnings, 3 rodadas estáveis. Ao final: tabelas vazias e nenhuma chave `lumini:*` no Redis.
- Adaptador (`tests/test_google_calendar.py`, transporte HTTP falso, chave RSA gerada na hora): paginação; eventos “disponível” e cancelados ignorados; dia inteiro ocupa o dia em Brasília; evento malformado, corpo inválido e excesso de páginas nunca viram tempo livre; 429/5xx/cota → indisponível, 403/404/400 → recusado, sem texto do Google na exceção; 401 renova o token uma vez; upsert PUT→POST→PUT; DELETE idempotente (200/204/404/410); `get_event`; transporte sem redirect, com timeout, corpo limitado a 1 MB e erros de rede sem causa encadeada; token emitido para o escopo `calendar.events` e o `token_uri` do Google, em cache até expirar; falhas do token sem texto do provedor; ids da Lumini reconhecidos só no formato exato.
- Configuração: chave aceita só se for de conta de serviço com `token_uri` do Google; erros e `repr` nunca mostram a chave.
- Worker: só as duas tarefas da Lumini registradas; beat com 60 s/900 s e expiração menor que o intervalo; sem credencial, a reconciliação não roda e o tick roda sem calendário. Encontrado e corrigido: tarefas Celery são compartilhadas entre apps por padrão; agora `shared=False`.
- Integração (`test_calendar_reconcile.py`): evento apagado no Google volta; evento movido volta ao horário reservado; evento de reserva cancelada que reapareceu é removido de novo; reservas em andamento/conflito não são tocadas; calendário fora do ar é pulado sem inferir nada; confirmação travada depois de o job desistir é reenfileirada (uma vez) e conclui; sem calendário o tick não cria conflito e a reserva expira por `calendar_timeout`; ciclos reais (`run_tick`/`run_reconcile`) com engine própria e trava Redis: o segundo ciclo concorrente é pulado.

## Worker real

`create_worker().worker_main([... "--beat" ...])` contra PostgreSQL/Redis locais, sem credencial do Google, por ~2 min: beat iniciou, tarefas `lumini.booking.tick` e `lumini.calendar.reconcile` registradas, tick executado a cada 60 s com sucesso (~40 ms), log só com contagens. Base Redis de teste limpa ao final.

## Não validado

Google Calendar real (conta de serviço, compartilhamento dos calendários, cotas, formato real das respostas), worker em Railway, TLS `rediss://` contra provedor remoto, envio de mensagens (T09), alerta para compromisso de terceiros sobre reserva confirmada (ADR-015).
