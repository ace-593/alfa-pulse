set -eu
cd "$(dirname "$0")/.."
git pull --ff-only
(cd backend && docker compose up -d --build --wait --wait-timeout 180)
(cd frontend && docker compose up -d --build --wait --wait-timeout 90)
