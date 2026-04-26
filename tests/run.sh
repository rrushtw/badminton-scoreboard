#!/usr/bin/env bash
# tests/run.sh — Spin up the docker-compose'd site and run the Playwright
# integration suite against it. Per CLAUDE.md, all Python runs in
# containers; nothing is installed on the host.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SITE_CONTAINER="badminton_scoreboard"
SITE_PORT_INTERNAL=8080
SITE_HOST_PORT=8889
PLAYWRIGHT_IMAGE="mcr.microsoft.com/playwright/python:v1.58.0-noble"

cleanup() {
    echo ">>> tearing down docker-compose stack"
    docker compose -f "$PROJECT_DIR/docker-compose.yml" down >/dev/null 2>&1 || true
}
trap cleanup EXIT

cd "$PROJECT_DIR"

echo ">>> docker compose up -d --build"
docker compose up -d --build

echo ">>> waiting for http://localhost:${SITE_HOST_PORT}/"
for _ in $(seq 1 30); do
    if curl -sf "http://localhost:${SITE_HOST_PORT}/" >/dev/null; then
        echo "    site is up"
        break
    fi
    sleep 1
done

NETWORK_NAME="$(docker inspect "$SITE_CONTAINER" \
    --format '{{range $name, $_ := .NetworkSettings.Networks}}{{$name}}{{end}}')"
echo ">>> site network: ${NETWORK_NAME}"

echo ">>> running playwright suite"
# The mcr.microsoft.com/playwright/python image bundles the browsers but
# not the Python bindings, so we install them inside the throwaway
# container from tests/requirements.txt (per CLAUDE.md, host stays untouched).
docker run --rm \
    --network "$NETWORK_NAME" \
    -v "$PROJECT_DIR/tests:/tests:ro" \
    -e SITE_URL="http://${SITE_CONTAINER}:${SITE_PORT_INTERNAL}" \
    -e PIP_DISABLE_PIP_VERSION_CHECK=1 \
    -e PIP_ROOT_USER_ACTION=ignore \
    "$PLAYWRIGHT_IMAGE" \
    bash -c "pip install --quiet --break-system-packages -r /tests/requirements.txt && python /tests/playwright/test_scoring.py -v"
