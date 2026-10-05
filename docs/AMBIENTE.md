# Ambiente local e retomada

Raiz: `/home/usuario/projects/lumini-clinica`.

## Ferramentas

- Python do sistema é 3.11.2. Backend terá Python 3.12 gerenciado por uv em ambiente isolado; não alterar Python do sistema.
- uv 0.12.21 instalado em `.tools/` (ignorado pelo Git). Em outra máquina, instalar uv pelo método oficial e usar `uv` no lugar de `../.tools/bin/uv`.
- Node do sistema é 18, insuficiente para a versão moderna do Next.js. Usar Node 22 já instalado:

```bash
export PATH="/home/usuario/.nvm/versions/node/v22.23.2/bin:$PATH"
node --version
```

O caminho acima é específico desta máquina. Em outra, usar Node 22 compatível e `npm ci`.

## Backend no VS Code

IDE escolhida pelo usuário em 2026-10-01: **VS Code**; PyCharm deixou de ser requisito (a instalação abaixo permanece apenas como histórico). Abrir a raiz do projeto e selecionar o interpretador `backend/.venv/bin/python`. A configuração de execução comum a qualquer IDE deve usar módulo `uvicorn`, argumentos `lumini.app:create_app --factory --reload --host 127.0.0.1 --port 8000 --no-access-log` e diretório de trabalho `backend/`.

Histórico: os recursos básicos do PyCharm bastam para abrir e executar o Python; recursos específicos de FastAPI podem depender da edição/plano. A instalação não é uma assinatura paga nem garante licença Pro. Primeiro início/termos/licença permanecem sob controle do usuário.

Instalação local realizada: PyCharm 2026.2.3 em `/home/usuario/.local/opt/pycharm-2026.2.3`, checksum oficial SHA256 conferido. Launcher `/home/usuario/.local/bin/pycharm-lumini` e entrada no menu de aplicativos. Processo iniciado com este projeto; configuração visual do interpretador ainda não comprovada.

## Claude e Remote Control

Claude Code 2.1.286, login Claude.ai verificado, conectado ao VS Code aberto na pasta Lumini. Ativação observada: `/remote-control is active`. O terminal da sessão foi aberto pelo Codex (PTY), com conexão à extensão do VS Code; não é uma aba de terminal integrada criada dentro do editor.

Para retomada quando não houver Claude rodando nesta pasta:

```bash
cd /home/usuario/projects/lumini-clinica
claude --continue --remote-control Lumini --no-chrome --ide
```

Somente executar quando a sessão anterior tiver encerrado; não iniciar duas sessões modificando o mesmo código. O comando retoma a conversa mais recente da pasta. A sessão lê `CLAUDE.md`; o ponto de retomada fica em `docs/HANDOFF.md`. URLs remotas e informações locais de autenticação não são versionadas.

## Serviços externos

Não há Docker, PostgreSQL ou Redis detectados no PATH desta máquina no início. A ausência não impede testes unitários, build do frontend e geração offline de migração. Testes de integração precisam de PostgreSQL e Redis reais (ou containers locais). Nunca substituir por SQLite e chamar isso de validação PostgreSQL.

Para o primeiro marco foram extraídos binários Debian em `/tmp/lumini-services.j2gMAS` e iniciados serviços isolados de teste, sem instalação de sistema. PostgreSQL15.19/Redis7.0.15 foram usados apenas em loopback, banco `lumini_foundation_test`, e **encerrados após os checks**. Para repetição durável, prover serviços locais/de CI próprios; o diretório em `/tmp` não é infraestrutura permanente. Testes exigem variáveis `LUMINI_INTEGRATION_DATABASE_URL` e `LUMINI_INTEGRATION_REDIS_URL`; `make backend-integration` executa somente essa suíte, sem limpar tabelas.

Receita usada (2026-10-05, após reboot apagar `/tmp`), sem root e só em loopback:

```bash
D=$(mktemp -d /tmp/lumini-services.XXXXXX); cd "$D"
apt-get download postgresql-15 postgresql-client-15 libpq5 libjemalloc2 liblua5.1-0 liblzf1
# A versão do Redis no índice local pode ter saído do espelho de segurança: fixar a disponível.
apt-get download redis-server=5:7.0.15-1~deb12u7 redis-tools=5:7.0.15-1~deb12u7
mkdir binaries && for pkg in ./*.deb; do dpkg-deb --extract "$pkg" binaries; done
export LD_LIBRARY_PATH=$D/binaries/usr/lib/x86_64-linux-gnu; B=$D/binaries/usr/lib/postgresql/15/bin
$B/initdb -D $D/pgdata -L $D/binaries/usr/share/postgresql/15 -U lumini_test --auth=trust --no-locale --encoding=UTF8
$B/pg_ctl -D $D/pgdata -l $D/postgres.log -o "-h 127.0.0.1 -p 55432 -k $D" -w start
$B/psql -h 127.0.0.1 -p 55432 -U lumini_test -d postgres -c "create database lumini_foundation_test"
$D/binaries/usr/bin/redis-server --bind 127.0.0.1 --port 56379 --save '' --appendonly no --daemonize yes --pidfile $D/redis.pid --logfile $D/redis.log
cd /home/usuario/projects/lumini-clinica/backend
LUMINI_DATABASE_URL=postgresql://lumini_test@127.0.0.1:55432/lumini_foundation_test ../.tools/bin/uv run --frozen alembic upgrade head
```

Para parar: `pg_ctl -D $D/pgdata -m fast -w stop` e `redis-cli -h 127.0.0.1 -p 56379 shutdown`. Ao usar `pkill -f`, não inclua no padrão um texto que também apareça no próprio comando do shell (ele se mata).

Evolution, Google Calendar, login Google e provedores de IA ainda precisam de configuração de teste própria da Lumini. Não copiar credenciais de projetos existentes. Configurar segredos pelo ambiente do processo/secret manager, nunca pelo chat. Nenhum acesso a Railway/Vercel foi solicitado neste marco.

## Referências de instalação verificadas

- uv: https://docs.astral.sh/uv/getting-started/installation/
- PyCharm: https://www.jetbrains.com/help/pycharm/installation-guide.html
- Next.js: https://nextjs.org/docs/app/getting-started/installation
- FastAPI: https://fastapi.tiangolo.com/deployment/docker/
