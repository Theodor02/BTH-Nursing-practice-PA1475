#!/usr/bin/env bash
set -euo pipefail

missing=0
warning=0

check_cmd() {
  local name=$1
  local version_cmd=$2

  if command -v "$name" >/dev/null 2>&1; then
    echo "[ok] $name: $($version_cmd 2>/dev/null | head -n 1)"
  else
    echo "[missing] $name"
    missing=1
  fi
}

check_cmd docker "docker --version"
check_cmd git "git --version"

if docker compose version >/dev/null 2>&1; then
  echo "[ok] docker compose: $(docker compose version | head -n 1)"
else
  echo "[missing] docker compose"
  missing=1
fi

if command -v docker >/dev/null 2>&1; then
  if docker info >/dev/null 2>&1; then
    echo "[ok] docker daemon: running"
  else
    echo "[warn] docker daemon is not running"
    warning=1
  fi
fi

if [[ $missing -eq 1 ]]; then
  echo
  echo "One or more prerequisites are missing."
  echo "Install Docker (with Compose) and Git, then try again."
  exit 1
fi

echo
if [[ $warning -eq 1 ]]; then
  echo "Prerequisites installed, but Docker is not running."
  echo "Start Docker Desktop (or docker daemon) before running 'docker compose up --build'."
else
  echo "All prerequisites are installed."
fi
