#!/usr/bin/env bash
# Restore a backup into an EMPTY database named by LUMINI_RESTORE_DATABASE_URL.
# Refuses to touch the source database or any database that already has tables.
set -euo pipefail
: "${LUMINI_RESTORE_DATABASE_URL:?LUMINI_RESTORE_DATABASE_URL is required}"
file="${1:?usage: restore.sh <backup.dump>}"
target="${LUMINI_RESTORE_DATABASE_URL/postgresql+asyncpg:/postgresql:}"
source="${LUMINI_DATABASE_URL:-}"
if [[ -n "$source" && "${source/postgresql+asyncpg:/postgresql:}" == "$target" ]]; then
  echo "refusing: restore target is the source database" >&2
  exit 2
fi
(cd "$(dirname "$file")" && sha256sum --check --quiet "$(basename "$file").sha256")
tables=$(psql --dbname="$target" --tuples-only --no-align --command \
  "select count(*) from information_schema.tables where table_schema = 'public'")
if [[ "$tables" != "0" ]]; then
  echo "refusing: restore target is not empty" >&2
  exit 3
fi
pg_restore --no-owner --no-privileges --exit-on-error --dbname="$target" "$file"
echo "restored"
