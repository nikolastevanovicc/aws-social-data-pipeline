#!/bin/bash
set -euo pipefail

superset db upgrade

if superset fab list-users | grep -Fq "username:${SUPERSET_ADMIN_USERNAME} "; then
  echo "Superset admin user ${SUPERSET_ADMIN_USERNAME} already exists."
else
  superset fab create-admin \
    --username "${SUPERSET_ADMIN_USERNAME}" \
    --firstname "${SUPERSET_ADMIN_FIRST_NAME}" \
    --lastname "${SUPERSET_ADMIN_LAST_NAME}" \
    --email "${SUPERSET_ADMIN_EMAIL}" \
    --password "${SUPERSET_ADMIN_PASSWORD}"
fi

superset init

superset run \
  --host 0.0.0.0 \
  --port 8088
