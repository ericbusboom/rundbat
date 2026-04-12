#!/bin/sh
set -e

# Decrypt secrets if age key is mounted
if [ -f /run/secrets/age-key ]; then
    export SOPS_AGE_KEY_FILE=/run/secrets/age-key
fi

exec "$@"
