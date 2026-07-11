#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

MAIN_FILE="apps/api/app/main.py"
if ! grep -q "patient360_router" "$MAIN_FILE"; then
  sed -i '/from app.core import router as core_router/a from app.patient360 import router as patient360_router' "$MAIN_FILE"
  sed -i '/app.include_router(core_router)/a app.include_router(patient360_router)' "$MAIN_FILE"
fi

CSS_FILE="apps/dashboard/app/globals.css"
MARKER="/* DentalFlow Step 7 Patient 360 */"
if ! grep -q "$MARKER" "$CSS_FILE"; then
  {
    echo
    echo "$MARKER"
    cat apps/dashboard/app/patient360-additions.css
  } >> "$CSS_FILE"
fi
rm -f apps/dashboard/app/patient360-additions.css
echo "Patient 360 installé."
