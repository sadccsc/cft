#!/usr/bin/env bash
set -euo pipefail

MAMBA_DIR="$HOME/.micromamba"

echo "Installing micromamba to $MAMBA_DIR ..."
curl -L https://micro.mamba.pm/install.sh | bash -s -- -b "$MAMBA_DIR"

# Load micromamba into *this* script immediately
eval "$($MAMBA_DIR/bin/micromamba shell hook --shell bash)"

# Create environment from YAML file
ENV_FILE="environment.yml"
if [[ -f "$ENV_FILE" ]]; then
    echo "Creating environment from $ENV_FILE ..."
    micromamba create -y -f "$ENV_FILE"
else
    echo "⚠️ No environment.yml found, skipping environment creation."
fi

# Add to shell profile for future sessions
PROFILE_FILE="$HOME/.bashrc"
if ! grep -q 'micromamba shell hook' "$PROFILE_FILE"; then
    {
        echo ''
        echo '# Micromamba setup'
        echo "eval \"\$($MAMBA_DIR/bin/micromamba shell hook --shell bash)\""
    } >> "$PROFILE_FILE"
fi

echo "✅ Micromamba installed and environment created!"
echo "💡 In new terminals, micromamba will be ready to use."
