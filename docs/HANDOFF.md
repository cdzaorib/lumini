# Handoff Lumini — atualizado a cada tarefa

Atualizado em **2026-10-14 — T12a/T12b e T13a–T13d concluídas localmente; lançamento depende de acessos e insumos externos** (Codex).

O escopo é o texto integral aprovado em `PLANO-ORIGINAL.md`. Preservar **Python/FastAPI, Celery/Redis e login Google**; frontend Vercel, PostgreSQL Supabase e API/worker/Redis Railway (ADR-019). Produção, GitHub público e push já autorizados; acesso a redes/contas autorizado nesta retomada. Nenhuma compra/upgrade autorizado. IDE **VS Code**; interpretador `backend/.venv/bin/python`. Não usar dados/infraestrutura/segredos de outros projetos.

## Resultado comprovado

- **Código entregue:** `0532dc2` consentimento opcional/revogável de analytics; `48ed326` classificador Jev separado, redator e bancada comparativa; `342b77b` revisão global do Site, fotos autorizadas/desacopladas, 12 textos operacionais revisados e histórico mínimo de encaminhamentos. Publicação só após aprovação de todas as profissionais verificadas e atribuição backend. Alteração/revogação/reverificação de credencial retira aprovação, sem republicar automaticamente. Saúde/STOP/reserva em processamento/sinal/regras/links/aftercare continuam determinísticos.
- **Real local:** Ruff/format (107 arquivos), mypy (105), **368 unitários e 202 integrações** PostgreSQL/Redis (`-W error`); migração **0010** e Alembic check sem drift; frontend ESLint/TypeScript/build Node 22.23.2/Next 16.3.8; E2E **7/7 cenários, 118/118 etapas**, console/CSP verdes. Check de consentimento confirma zero chamadas antes do aceite, recusa/revogação/reload/abas/quota, payload mínimo e rotas sensíveis; allowlist de mídia passou. Gitleaks por staging e histórico **26 commits**, sem vazamento.
- **Produção local simulada:** instalação independente `uv sync --frozen --no-dev`, 49 pacotes; live/ready 200, admin anônimo 401, docs/OpenAPI 404. Nenhuma suite destrutiva foi rodada contra produção.
- **Real na nuvem:** GitHub público `https://github.com/cdzaorib/lumini`, origin HTTPS, histórico preservado, push de main sem force. CI do código `342b77bc7313f8e4e29b8972e91de417b6252949` **verde**: [run 38577525488](https://github.com/cdzaorib/lumini/actions/runs/38577525488), secrets/backend/frontend. Vercel existente `lumini`/equipe `cdzaoribs-projects`, projeto `prj_QLNtFWbhZcQbEY9xic5IqnMOZoVY`; deployment **dpl_aJvWeqHA7TLrNEiwBoJyY8jyRWY6 READY**, target production, fonte nesse commit. Origem `https://lumini-cdzaoribs-projects.vercel.app` (alias `lumini-taupe.vercel.app`), SSO mantido, indexação fechada. Fetch autenticado validou home/controle de privacidade, admin não configurado, reserva e robots. **Frontend protegido e parcial: sem API/banco/fornecedores, não constitui lançamento.**
- **Apenas preparado:** Railway API/worker/Redis; banco Supabase exclusivo; Google/WhatsApp/IA/storage/analytics reais. Meta Pixel só parser de configuração, **sem runtime/tag**; ativação futura depende de campanha/contrato/consentimento separado.
- **Mock/sintético:** identidade Google, Google Calendar, Evolution, IA e dados dos testes. Nenhuma chamada autenticada real desses fornecedores; nenhum conteúdo/credencial clínica verificado por um teste fake.

A afirmação antiga de que todo código estava pronto foi corrigida pela auditoria. Lacunas locais foram implementadas e revisadas; o plano integral ainda exige integrações reais, incluindo **Jev, DeepSeek, seleção de fallback e analytics**. Manter IA/medição desligadas até cumprir os gates não dispensa essas entregas. Não apresentar a entrega local como produto clínico lançado.

## Pendências exatas e próximo passo

**Lista executável: `PENDENCIAS.md`.** Primeiro resolver conexão Railway e escolha explícita da organização/custo Supabase; depois provisionar Lumini exclusivo e seguir `DEPLOY.md`. É possível retomar a publicação já autorizada quando esses acessos estiverem disponíveis. Não reabrir produto/stack nem pedir tokens no chat.

1. **Railway:** plugin instalado/desconectado (`USER_NOT_LOGGED_IN`); nenhum token/serviço Lumini. Conectar conta em Apps/Plugins, conferir workspace/plano antes de criar API/worker/Redis.
2. **Supabase:** conectado, sem Lumini; organização acessível `relatorio de passagens` (`afuprpdipwmfssxmlcdq`, Free). Conector exige organização escolhida e custo consultado/confirmado; não presumir quota/preço, apagar ou reutilizar outros bancos.
3. **Navegador:** CUA sem superfícies; Chrome e navegador integrado indisponíveis. Não foi possível operar Google Cloud/QR/DNS ou conectar Git na Vercel por dashboard. Autorização de acesso não disponibiliza sessão autenticada.
4. **Clínica/provedores:** Google OAuth/allowlist/atribuições e conta de serviço/calendários; Evolution/número de teste/PoC; chaves/modelos/bancada IA; matriz/preços/sinais/credenciais profissionais/contatos/endereço/horários/Pix/textos e fotos/depoimentos autorizados; storage/CDN próprio.
5. **Antes de abrir:** políticas/retenção jurídica, backups reais e restauração isolada, teste com leitor de tela/desempenho publicado, piloto e aprovação final clínica. IA permanece desligada até a avaliação. Base44 permanece como entrada até fluxo completo aprovado.

O deploy explícito por commit GitHub funciona. O contexto Git Vercel não lista Lumini como projeto ligado: push sozinho **não** prova deploy automático. Conectar repo ao projeto existente quando dashboard estiver disponível. `LUMINI_PUBLIC_SITE_URL` Production configurada com a origem real acima; API/Google/mídia/analytics continuam sem valores inventados.

## Limitações registradas

- Auditoria npm de produção (`--omit=dev`) sem avisos; auditoria completa aponta cinco entradas altas na cadeia dev/lint braces 3.0.3, sem patch publicado, [GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm). Downgrade incompatível sugerido pelo npm não aplicado. ESLint 9 EOL segue por compatibilidade dos plugins. Ver manutenção em PENDENCIAS; não afirmar auditoria completa verde.
- Primeira cópia E2E usou symlink node_modules externo, recusado pelo Turbopack. Instalação dentro da cópia resolveu; rodada completa passou. Nenhuma alteração de produto para mascarar erro de ambiente.
- Retirada de conteúdo descarta replies pendentes e incrementa versões sem reativar modo humano. Não há garantia distribuída de desfazer envio já em andamento. Histórico guarda só etapa/UUIDs; métrica de encaminhamentos é WhatsApp desde 0010, sem passado inventado. Histórico web expira em 1 dia.
- Sem orçamento real medido, assinatura/storage/domínio adquirido, fornecedor real comprovado, backup remoto ou migração de nuvem. Conteúdo legal/clinical não é aprovado por build.

## Git, processos e retomada

- Branch **main**, origin `https://github.com/cdzaorib/lumini.git`; código de produto até **342b77b**, documentação desta retomada em commit posterior. Inspecionar HEAD/status antes de continuar; não force push. Dependências/lockfiles preservados.
- **Nenhum serviço Lumini de validação ativo:** PostgreSQL/Redis sintéticos, Next/API E2E, Next 3117 e API production 8200 iniciados nesta tarefa foram encerrados; portas 3000/3100/3117/55432/56379/8100/8200 conferidas livres. Processos de outras aplicações preservados.
- Evidências/capturas: `/tmp/lumini-final-20261014-imrh92bc/e2e/.output/`; copia/venvs/serviços são temporários e não infraestrutura permanente. Receita local em `AMBIENTE.md`.
- Subagentes concluíram e liberaram arquivos; coordenador revisou fixes e manteve docs/commits. Não retomar edições paralelas sobre o mesmo arquivo.
- Leia `PLANO.md`, `PLANO-ORIGINAL.md`, `DECISOES.md`, `TAREFAS.md`, `LANCAMENTO.md`, `DEPLOY.md` e `PENDENCIAS.md`; conferir Git/processos. Desenvolvimento sintético e publicação previamente autorizados, compra/upgrade não. Migração remota explícita só após banco dedicado/vazio, Data API desligada e conexão TLS comprovada; nunca rodar suites de integração/E2E contra produção.

Regras permanentes em AGENTS; contratos em API-ADMIN; ADR-020–023 registram decisões desta retomada. Histórico anterior em VALIDACAO-001–008. TAREFAS/HANDOFF devem ser atualizados a cada tarefa concluída ou bloqueada.

## Auditoria de conclusão T14b

Retomada automática conferiu `main` limpa em e8b841a, sem processos de teste ativos. Railway continua `USER_NOT_LOGGED_IN`, Supabase continua sem Lumini e inventário CUA permanece vazio. Escolha da organização Supabase foi solicitada ao usuário porque o contrato do conector a exige antes de consultar custo; não há resposta que autorize assumir essa escolha. Auditoria independente corrigiu dois rótulos que tratavam indevidamente IA/analytics como opcionais. Requisitos reais/critério de prova registrados em LANCAMENTO; **objetivo integral ainda não comprovado**.
