#!/usr/bin/env bash
# Populate dotconfig with example config for each deployment.
# Values are named so you can tell at a glance which deployment they came from.
set -euo pipefail

cd "$(dirname "$0")/.."

for deploy in dev prod; do
    echo "--- Setting up $deploy ---"

    cat > .env <<EOF
# CONFIG_DEPLOY=$deploy

#@dotconfig: public ($deploy)
FOO=${deploy}-foo-public
BAR=${deploy}-bar-public

#@dotconfig: secrets ($deploy)
FOO_SECRET=${deploy}-foo-secret
BAR_SECRET=${deploy}-bar-secret
EOF

    dotconfig save
done

# Local developer overlay (eric)
echo "--- Setting up local/eric ---"

cat > .env <<EOF
# CONFIG_DEPLOY=dev
# CONFIG_LOCAL=eric

#@dotconfig: public (dev)
FOO=dev-foo-public
BAR=dev-bar-public

#@dotconfig: secrets (dev)
FOO_SECRET=dev-foo-secret
BAR_SECRET=dev-bar-secret

#@dotconfig: public-local (eric)
FOO=eric-foo-local
BAR=eric-bar-local

#@dotconfig: secrets-local (eric)
FOO_SECRET=eric-foo-secret-local
BAR_SECRET=eric-bar-secret-local
EOF

dotconfig save

rm -f .env
echo "Done. Run 'dotconfig load -d <deploy> -S' to verify."
