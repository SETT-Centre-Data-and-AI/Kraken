#!/bin/bash
# Runs after Python/tooling install and before package install.

set -euo pipefail

echo "[pre-install] Starting pre-install hook"

if [[ "${RUNNER_OS:-}" != "Linux" ]]; then
	echo "[pre-install] Non-Linux runner detected. Skipping Linux dependency setup."
	exit 0
fi

echo "[pre-install] Installing Ubuntu system dependencies"
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -y
sudo apt-get install -y --no-install-recommends \
	libmariadb3 libmariadb-dev \
	unixodbc unixodbc-dev

echo "[pre-install] Configuring keyring backend for CI"
if [[ -n "${GITHUB_ENV:-}" ]]; then
	echo "PYTHON_KEYRING_BACKEND=keyrings.alt.file.PlaintextKeyring" >> "$GITHUB_ENV"
fi
export PYTHON_KEYRING_BACKEND=keyrings.alt.file.PlaintextKeyring

if python -c "import keyrings.alt" >/dev/null 2>&1; then
	echo "[pre-install] keyrings.alt already available"
else
	echo "[pre-install] Installing keyrings.alt"
	python -m pip install --upgrade keyrings.alt
fi

echo "[pre-install] Complete"
