set -eu
cd "$(dirname "$0")/.."
umask 077
mkdir -p backups
target="backups/pulse-$(date -u +%Y%m%dT%H%M%SZ).dump"
docker compose -f backend/compose.yaml exec -T postgres pg_dump -U pulse -d pulse -Fc > "$target"
test -s "$target"
printf '%s\n' "$target"
