#!/usr/bin/env bash
# Logical backup of the Lumini database (pg_dump custom format) with a SHA-256 checksum.
# Reads LUMINI_DATABASE_URL from the environment and never prints it. The dump contains personal
# data: keep it only in encrypted storage with restricted access (docs/RUNBOOK-BACKUP.md).
set -euo pipefail
: "${LUMINI_DATABASE_URL:?LUMINI_DATABASE_URL is required}"
out_dir="${1:?usage: backup.sh <output-dir>}"
umask 077
mkdir -p "$out_dir"
chmod 700 "$out_dir"
url="${LUMINI_DATABASE_URL/postgresql+asyncpg:/postgresql:}"
file="$out_dir/lumini-$(date -u +%Y%m%dT%H%M%SZ).dump"
pg_dump --format=custom --no-owner --no-privileges --dbname="$url" --file="$file"
(cd "$out_dir" && sha256sum "$(basename "$file")" > "$(basename "$file").sha256")
echo "$file"
