set -eu
cd "$(dirname "$0")/.."
git pull --ff-only
docker compose up -d --build --wait --wait-timeout 180
