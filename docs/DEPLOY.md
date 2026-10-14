# Preparação de publicação — atualizado em 2026-10-14

## Retomada T12a/T12b/T13

GitHub público criado e `main` enviada com histórico integral: `https://github.com/cdzaorib/lumini`; CLI autenticado. CI do baseline `7fddf38` verde (run 38570501448). Vercel existente tem primeiro deployment **READY**, protegido, na origem real `https://lumini-cdzaoribs-projects.vercel.app`; indexação fechada. `LUMINI_PUBLIC_SITE_URL` dessa origem configurada somente em Production. API/banco/worker ainda não existem: isso não é lançamento funcional.

O contexto Git da Vercel ainda não lista Lumini como vinculado. Deploy explícito a partir do commit GitHub funciona; para automação de pushes, conectar `cdzaorib/lumini` no projeto existente (Settings → Git) quando o navegador estiver disponível. Não duplicar o projeto. Railway segue desconectado, nenhum navegador CUA disponível, nenhum projeto Supabase Lumini e nenhuma credencial Lumini no ambiente. Tarefas externas detalhadas em `PENDENCIAS.md`.

## Escopo e auditoria

O usuário autorizou deploy de produção, criação de repositório GitHub **público**, commits e push sem reescrever histórico. Após a auditoria, confirmou preservar **FastAPI + Celery/Redis + login Google**, hospedar o PostgreSQL no **Supabase**, frontend na **Vercel**, API/worker no **Railway** (ADR-019). Não há reimplementação ou mudança de dependências.

- Checkout: `/home/usuario/projects/lumini-clinica`; branch `main`; início em `9ea0aa7`, árvore limpa e **sem remote**. Histórico existente deve ser enviado integralmente após autenticação e criação do repositório.
- Frontend: Next.js App Router 16.3.8, React 19.3.0, TypeScript 6.0.3, Tailwind 4.3.3. Node `>=22.23.2 <23`; `frontend/package-lock.json`. Scripts `lint`, `typecheck`, `build`, `start`, `dev`; não há `npm test`.
- Backend: Python 3.12, FastAPI, SQLAlchemy/asyncpg, Alembic, Celery/Redis; `backend/uv.lock`. API e worker compartilham o pacote.
- Banco: migrações existentes até `0008_calendar_overlap`. A integridade de reservas depende de PostgreSQL `EXCLUDE USING gist`/`btree_gist`; não substituir por trava Redis.
- Auth: Google ID token em memória, allowlist/verificação no FastAPI. Não existe cadastro público de contas. Logout limpa o token local.
- Supabase: nenhuma dependência, cliente, Auth, Storage, callback Supabase ou chave Supabase no código auditado. Será usado como PostgreSQL via `LUMINI_DATABASE_URL`.
- Assets: ícone SVG e elementos CSS locais; fotos/storage da clínica ainda não configurados. Conteúdo e páginas legais têm pendências descritas em `LANCAMENTO.md`.
- Segurança: gitleaks varreu os 22 commits iniciais, sem vazamentos; busca complementar de padrões de chaves no checkout não encontrou credenciais. `.env`/`.env.*` são ignorados, exceto exemplos; `.vercel/` agora também é ignorado. Nenhum segredo foi copiado ou criado em `.env`.

## Vercel

Projeto **lumini**, ID `prj_QLNtFWbhZcQbEY9xic5IqnMOZoVY`, equipe `cdzaoribs-projects` (`team_3qD3d4yDGS6JTl7IIvMmEMwy`). Não existia Lumini nos projetos acessíveis; criado nesta tarefa.

| Campo | Configuração |
|---|---|
| Framework | Next.js |
| Root Directory | `frontend` |
| Node | `22.x` |
| Install | `npm ci` |
| Build | `npm run build` |
| Output | Automático do Next.js; sem override/export estático |
| Git | GitHub criado/push realizado; associação automática Vercel pendente |
| Deploy / URL | Primeiro frontend READY e protegido; origem real validada acima; sem API |

Configuração versionada em `frontend/vercel.json`; `.vercelignore` exclui ambientes e artefatos locais de uploads CLI. O projeto mantém a proteção de deploy padrão da equipe; conferir o acesso anônimo ao `.vercel.app` antes de declarar o site público.

Variáveis realmente lidas pelo frontend (as marcadas pendentes **não foram preenchidas com placeholders na nuvem**):

| Nome | Onde | Estado / finalidade |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | Production e Preview | Pendente: origem HTTPS da API de cada ambiente; libera formulário/chat/painel |
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | Production e Preview | Pendente: Client ID Google real do ambiente, igual ao backend |
| `LUMINI_PUBLIC_SITE_URL` | Cada ambiente | Production configurada com a origem real validada; Preview só quando sua origem estiver definida |
| `LUMINI_SITE_STAGE` | Production e Preview | Configurada por ambiente; produção oculta avisos internos, preview mostra pendências |
| `LUMINI_SITE_PUBLIC` | Production e Preview | Configurada: indexação fechada até critérios de `LANCAMENTO.md` |
| `LUMINI_API_INTERNAL_URL` | Servidor Next, opcional | Não configurada; só usar URL comprovadamente acessível pela Vercel, sem credenciais. Uma URL privada Railway não é acessível automaticamente pela Vercel |
| `LUMINI_MEDIA_ORIGINS` | Servidor Next/build | JSON de origens HTTPS do storage/CDN da clínica; igual à allowlist backend. Ausente = fotos ocultas. Não contém chave nem query; Next não segue redirects |
| `NEXT_PUBLIC_PLAUSIBLE_DOMAIN` | Public config do frontend | Pendente: domínio cadastrado no Plausible pela clínica, necessário para completar analytics; sem conta/valor = medição provisoriamente desligada. Só `/`, com consentimento explícito |

`NODE_ENV` é gerenciado pela plataforma. `NEXT_TELEMETRY_DISABLED` é opcional para ferramentas de build, não funcionalidade. Não adicionar `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` ou `SUPABASE_SERVICE_ROLE_KEY`: não são usadas nesta arquitetura. Nenhuma URL de banco, Redis, chave de agenda ou Evolution pertence à Vercel.

## Supabase: configuração antes das migrações

Criação de projeto exclusivo `lumini` autorizada pelo usuário; ainda depende de confirmar organização e custo pelo conector. Não reutilizar os projetos de outros produtos listados na conta. A única organização acessível nesta auditoria é `relatorio de passagens` (`afuprpdipwmfssxmlcdq`); a escolha está pendente, não presumida.

Após criação, fazer nesta ordem:

1. Confirmar o project ref e a região São Paulo (`sa-east-1`), sem modificar projetos existentes.
2. Em **Integrations → Data API**, desligar **Enable Data API**: toda leitura/escrita passa pelo FastAPI. Confirmar que os endpoints REST não expõem as tabelas. Verificar grants a `anon`/`authenticated` e advisors antes de liberar a API.
3. Em **Connect**, copiar a conexão **direta** se o host Railway tiver IPv6, ou **Session pooler** se for IPv4. Não usar Transaction pooler com a configuração atual do asyncpg/prepared statements. Configurar TLS com validação do certificado (`ssl=verify-full`) e o host/usuário fornecidos pelo painel. Guardar a URL somente como `LUMINI_DATABASE_URL` no gerenciador de segredos da API e do worker.
4. Validar conexão, extensão `btree_gist` e banco vazio/dedicado. Inspecionar `alembic current` antes de executar as migrações existentes com `uv run --frozen --no-sync alembic upgrade head`; conferir `alembic check` e readiness. Não executar as suites de integração/E2E contra produção: elas apagam/recriam dados de teste.
5. Configurar backups de produção e ensaio de restauração isolado (`RUNBOOK-BACKUP.md`).

Supabase Auth e Storage não exigem configuração nesta arquitetura. Não há redirect/callback Supabase a preencher; não criar políticas de acesso do frontend nem expor uma service role.

Referências: [conexão PostgreSQL](https://supabase.com/docs/guides/database/connecting-to-postgres), [desativar/proteger Data API](https://supabase.com/docs/guides/api/securing-your-api).

## Railway e Google

O conector Railway retornou `USER_NOT_LOGGED_IN`. Nenhum projeto, serviço, banco ou deploy Railway foi criado. Após conectar a conta, verificar workspace, projetos existentes e disponibilidade/plano antes de provisionar; não comprar/alterar assinatura automaticamente.

Criar/reutilizar o projeto Lumini exclusivo, com serviços `api`, `worker` e Redis. API e worker usam o mesmo repositório/branch `main`, root `/backend`, config files `/backend/railway.api.json` e `/backend/railway.worker.json`. Builder Railpack suporta `pyproject.toml` + `uv.lock`; build `uv sync --frozen --no-dev`. Manter serviços contínuos (sem sleep), **um** worker/beat e uma réplica. API recebe domínio HTTPS e healthcheck `/health/ready`; worker não recebe domínio. Referenciar o Redis privado do mesmo projeto em `LUMINI_REDIS_URL`, sem publicar sua porta.

Não há migration pre-deploy automática; a inicialização do banco deve ser conferida e executada separadamente. Readiness testa PostgreSQL e Redis, sem provar Google/WhatsApp/auth/schema.

| Variável backend | Serviço | Necessidade |
|---|---|---|
| `LUMINI_ENVIRONMENT` | API/worker | Configurar modo production |
| `LUMINI_DATABASE_URL` | API/worker/migrações | Pendente: conexão Supabase, segredo |
| `LUMINI_REDIS_URL` | API/worker | Pendente: Redis do projeto, segredo |
| `LUMINI_CORS_ORIGINS` | API | JSON de origens HTTPS reais e explícitas; não wildcard |
| `LUMINI_MEDIA_ORIGINS` | API/worker | JSON de origens HTTPS explícitas para fotos; nenhuma origem de outro projeto; publicação recusa origem ausente |
| `LUMINI_GOOGLE_CLIENT_ID` | API | Pendente: Client ID Google |
| `LUMINI_ADMIN_EMAILS` | API | Pendente: JSON de administradores Gmail/Workspace autorizados |
| `LUMINI_REVIEWER_ASSIGNMENTS` | API | JSON email → UUIDs das profissionais aprovadas, após cadastro; não inventar atribuições |
| `LUMINI_GOOGLE_CALENDAR_CREDENTIALS` | API/worker | Pendente: JSON da conta de serviço Google da clínica, segredo; necessário para agenda real |
| `LUMINI_MANAGE_LINK_SECRET` | API/worker | Pendente: segredo aleatório 32+ caracteres, gerenciado fora do Git/chat |
| `LUMINI_PUBLIC_SITE_URL` | API/worker | Pendente: origem real do frontend; links de autoatendimento |
| `LUMINI_EVOLUTION_BASE_URL` | API/worker | Se WhatsApp habilitado: origem real HTTPS |
| `LUMINI_EVOLUTION_INSTANCE` | API/worker | Se WhatsApp habilitado: instância exclusiva verificada |
| `LUMINI_EVOLUTION_API_KEY` | API/worker | Se WhatsApp habilitado: segredo |
| `LUMINI_EVOLUTION_WEBHOOK_TOKEN` | API | Se WhatsApp habilitado: segredo 32+ caracteres |
| `LUMINI_AI_ENABLED` | API/worker | Padrão desligado; manter até bancada real aprovada |
| `LUMINI_AI_BASE_URL` | API/worker | Só quando IA autorizada/habilitada |
| `LUMINI_AI_API_KEY` | API/worker | Só quando IA autorizada/habilitada; segredo |
| `LUMINI_AI_CLASSIFIER_MODEL` | API/worker | Só quando IA autorizada/habilitada |
| `LUMINI_AI_CLASSIFIER_PROVIDER` | API/worker | `openai` preserva adaptador existente; `jev` usa API estruturada separada; padrão `openai` |
| `LUMINI_JEV_API_KEY` | API/worker | Chave Jev só pelo gerenciador de segredos; nenhuma chave criada/obtida |
| `LUMINI_JEV_MODEL` | API/worker | Modelo real descoberto por `/v1/models` autenticado; nenhum default inventado |
| `LUMINI_AI_WRITER_MODEL` | API/worker | Só quando IA autorizada/habilitada |
| `LUMINI_DEPENDENCY_TIMEOUT_SECONDS` | API/worker | Opcional: padrão existente 2 s |
| `LUMINI_AI_HIGH_CONFIDENCE` | API/worker | Opcional: padrão existente não calibrado |
| `LUMINI_AI_MEDIUM_CONFIDENCE` | API/worker | Opcional: padrão existente não calibrado |

Google Cloud: Client ID OAuth de **aplicação web**, com **Authorized JavaScript origins** contendo a origem exata de produção e as origens Preview usadas nos testes (não wildcard). O fluxo atual GIS ID token não implementa callback OAuth/redirect próprio. Mesmo Client ID no Next e no FastAPI. Compartilhar os calendários das profissionais com a conta de serviço com permissão de edição; ativar Calendar API e executar teste controlado. Sem credenciais reais, não declarar login/agenda validados.

Referências: [configuração Railway](https://docs.railway.com/config-as-code), [Python/uv no Railpack](https://railpack.com/languages/python/).

## GitHub e domínio

GitHub CLI e conector agora autenticados como `cdzaorib`. Repositório público exclusivo `cdzaorib/lumini` criado vazio e histórico enviado sem force push. Baseline T12 passou no CI remoto. Nenhum novo login/token manual GitHub é necessário nesta retomada. Navegador indisponível é uma limitação distinta, que impede as etapas de dashboard dos demais fornecedores.

Remote `origin` já aponta a `https://github.com/cdzaorib/lumini.git`; main segue origin/main. Conferir estado antes de novos pushes; nunca force push. Conectar esse repositório ao projeto Vercel existente e usar `main` como Production Branch; até isso, acionar deployments explícitos pelo commit GitHub.

`.vercel.app` real validado com proteção SSO mantida; nenhum domínio próprio confirmado/adquirido. Para futuro domínio **já pertencente à clínica**, em Vercel → lumini → Settings → Domains adicionar apex/www autorizados, escolher canônico e copiar exatamente A/CNAME mostrados para o provedor DNS, preservando MX/TXT existentes. Aguardar verificação/HTTPS; atualizar Google/CORS/origem pública, redeploy e testar redirects. `lumini.com.br` é apenas exemplo histórico, não afirma disponibilidade/propriedade. Nenhuma compra autorizada.

Referência: [adicionar domínio Vercel](https://vercel.com/docs/domains/working-with-domains/add-a-domain).

## Validação local e limites

- `npm ci` com Node 22.23.2: passou; aviso conhecido de EOL do ESLint 9, sem mudança de dependências/lockfiles.
- `npm run lint` e `npm run typecheck`: passaram.
- `npm run build`: passou em cópia isolada após retirar o cache da tentativa bloqueada pelo sandbox. Nenhuma correção de código necessária para o build.
- Ruff check/format: passaram (98 arquivos); mypy: passou (96 arquivos).
- `pytest -W error`: **299 passaram**, 189 integrações deselected.
- `pytest -m integration -W error`: **189 passaram**, 299 unitários deselected, usando PostgreSQL/Redis locais sintéticos.
- `uv sync --frozen --no-dev`: instalação de produção passou em ambiente virtual temporário; isso não prova build Railpack remoto.
- E2E: resultado final e limitações serão registrados em `TAREFAS.md`/`HANDOFF.md` ao encerrar a validação.

Testes não validam fornecedores reais. Login Google é stub, Google Calendar em memória, Evolution simulado, IA desligada. Não há smoke test de produção sem deploy. Após publicação, validar home, navegação, catálogo, assets, formulário e escrita/leitura controlada no Supabase via FastAPI, login Google real/logout/rotas protegidas, agenda/autoatendimento e console/HTTP sem falhas. Usar dados sintéticos de teste controlado, sem rodar E2E destrutivo em produção.

## Bancada IA e mídia antes da habilitação real

Jev agora tem cliente próprio, contrato verificado; IA continua desligada. Chaves/modelos configurados por ambiente de processo/gerenciador, rodar no backend `uv run --frozen python -m lumini.ai.evaluation --label <candidato>`; a CLI habilita chamadas apenas para essa bancada sintética, sem alterar a aplicação. Preços verificados por modelo via `--price MODEL INPUT OUTPUT` (USD por milhão de tokens); falta de preço/usage aparece como custo incompleto. Comparação offline `--compare <relatorios-numericos>`; revisar segurança/minimização/qualidade/latência e escolher fallback antes de habilitar runtime. Nunca registrar prompts/respostas ou usar clientes reais na bancada.

Fotos exigem storage/CDN exclusivo escolhido pela clínica, URLs públicas sem segredo, dimensões/alt e autorização registrada no painel. Configurar a origem nas duas allowlists e submeter a revisão global por todas as profissionais verificadas. Nenhum upload/conta/storage de outro projeto foi reutilizado. Meta Pixel tem somente parser de configuração, **sem tag/runtime**; ativação futura exige campanha e consentimento separado, com contrato oficial verificado. Não adicionar variáveis Meta à nuvem como se produzissem uma integração ativa.
