#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
migration_tmp_root=${BUSANLINK_MIGRATION_TMP_ROOT:-/private/tmp}
migration_tmp_dir=$(mktemp -d "$migration_tmp_root/busanlink-migrations.XXXXXX")
database_dir="$migration_tmp_dir/data"
database_log="$migration_tmp_dir/postgres.log"

cleanup() {
    if [[ -d "$database_dir" ]]; then
        pg_ctl -D "$database_dir" stop -m fast >/dev/null 2>&1 || true
    fi

    case "$migration_tmp_dir" in
        */busanlink-migrations.*) rm -rf -- "$migration_tmp_dir" ;;
        *) echo "Refusing to remove unexpected temp path: $migration_tmp_dir" >&2 ;;
    esac
}
trap cleanup EXIT

for command_name in initdb pg_ctl psql; do
    if ! command -v "$command_name" >/dev/null 2>&1; then
        echo "Missing required command: $command_name" >&2
        exit 1
    fi
done

initdb -D "$database_dir" --no-locale --encoding=UTF8 >/dev/null
pg_ctl \
    -D "$database_dir" \
    -l "$database_log" \
    -o "-F -p 55432 -k $migration_tmp_dir -c listen_addresses=''" \
    start >/dev/null

psql_args=(-X -v ON_ERROR_STOP=1 -h "$migration_tmp_dir" -p 55432 postgres)

psql "${psql_args[@]}" -c "
    create role anon nologin;
    create role authenticated nologin;
    create schema auth;
    create table auth.users (id uuid primary key, email text);
    create function auth.uid() returns uuid language sql stable
    as 'select nullif(current_setting(''request.jwt.claim.sub'', true), '''')::uuid';
" >/dev/null

for migration_file in "$repo_root"/supabase/migrations/*.sql; do
    echo "Applying $(basename "$migration_file")"
    psql "${psql_args[@]}" -f "$migration_file" >/dev/null
done

psql "${psql_args[@]}" -f "$repo_root/supabase/tests/database_schema_test.sql"
