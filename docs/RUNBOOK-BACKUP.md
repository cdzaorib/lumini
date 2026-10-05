# Manual de operação — backup e restauração do banco

Para quem administra a infraestrutura. O dump contém dados pessoais (nomes, telefones, reservas): guarde apenas em armazenamento criptografado, com acesso individual e restrito, e apague cópias locais depois do uso.

## Backup

```bash
LUMINI_DATABASE_URL=<do gerenciador de segredos> infrastructure/backup/backup.sh <pasta-segura>
```

Gera `lumini-<data UTC>.dump` (formato custom do `pg_dump`, sem dono/privilégios) e `.sha256`. Pasta 700, arquivos 600. A URL do banco nunca é impressa.

Produção: além deste dump lógico, ativar e **verificar** os backups automáticos do provedor do PostgreSQL (Railway) e definir frequência, retenção e quem pode restaurar. Pendente até o deploy ser autorizado.

## Restauração (sempre num banco novo e vazio)

```bash
LUMINI_DATABASE_URL=<origem, para a trava de segurança> \
LUMINI_RESTORE_DATABASE_URL=<banco vazio de destino> \
infrastructure/backup/restore.sh <arquivo.dump>
```

O script confere o checksum, recusa destino igual à origem (saída 2) e destino com tabelas (saída 3), e para no primeiro erro. Depois de restaurar: conferir `alembic current`, contagem das tabelas principais e subir a API apontando para o banco restaurado em ambiente separado antes de qualquer troca.

## Ensaio

Fazer um ensaio completo antes do lançamento e depois a cada trimestre, registrando data, tamanho, tempo e resultado em `docs/TAREFAS.md`. Último ensaio local: `VALIDACAO-007.md`.
