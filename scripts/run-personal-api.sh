#!/bin/bash
set -euo pipefail
DATA_DIR="$HOME/personal-data"
set -a
. "$DATA_DIR/vocabulary-api.env"
set +a
echo $$ > "$DATA_DIR/vocabulary-api.pid"
exec /usr/bin/python3 -u "$HOME/personal/server/vocabulary_api.py"
