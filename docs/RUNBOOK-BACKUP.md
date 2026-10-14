# Manual de operação — backup e restauração do banco

Para quem administra a infraestrutura. O dump contém dados pessoais (nomes, telefones, reservas): guarde apenas em armazenamento criptografado, com acesso individual e restrito, e apague cópias locais depois do uso.

## Backup

```bash
LUMINI_DATABASE_URL=<do gerenciador de segredos> infrastructure/backup/backup.sh <pasta-segura>
```

Gera `lumini-<data UTC>.dump` (formato custom do `pg_dump`, sem dono/privilégios) e `.sha256`. Pasta 700, arquivos 600. A URL do banco nunca é impressa.

Produção: além deste dump lógico, confirmar a disponibilidade/custo e **verificar** os backups do provedor PostgreSQL (Supabase, ADR-019), definir frequência, retenção e quem pode restaurar. Não presumir backup automático no plano Free; um destino externo criptografado e o agendamento do dump precisam ser configurados se a cobertura do plano não atender. Publicação já autorizada; falta provisionar o banco e comprovar a restauração isolada.

Documentação atual consultada: [Database Backups — Supabase](https://supabase.com/docs/guides/platform/backups), que orienta exportações e cópias fora do provedor para o plano Free. Backups do banco não incluem os arquivos de fotos do storage/CDN: guardar cópias autorizadas desses assets separadamente.

## Restauração (sempre num banco novo e vazio)

```bash
LUMINI_DATABASE_URL=<origem, para a trava de segurança> \
LUMINI_RESTORE_DATABASE_URL=<banco vazio de destino> \
infrastructure/backup/restore.sh <arquivo.dump>
```

O script confere o checksum, recusa destino igual à origem (saída 2) e destino com tabelas (saída 3), e para no primeiro erro. Depois de restaurar: conferir `alembic current`, contagem das tabelas principais e subir a API apontando para o banco restaurado em ambiente separado antes de qualquer troca.

## Ensaio

Fazer um ensaio completo antes do lançamento e depois a cada trimestre, registrando data, tamanho, tempo e resultado em `docs/TAREFAS.md`. Último ensaio local: `VALIDACAO-007.md`.
