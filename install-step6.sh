#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

CSS_FILE="apps/dashboard/app/globals.css"
IMPORT_MARKER="/* DentalFlow Step 6 Calendar */"

if ! grep -q "$IMPORT_MARKER" "$CSS_FILE"; then
  {
    echo
    echo "$IMPORT_MARKER"
    cat apps/dashboard/app/calendar-additions.css
  } >> "$CSS_FILE"
fi

rm -f apps/dashboard/app/calendar-additions.css

echo "Étape 6 installée."
