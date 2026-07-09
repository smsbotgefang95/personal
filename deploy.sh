#!/bin/bash

# Exit immediately if any command fails
set -e

# --- Configuration Variables ---
DOMAIN="personal.homehomehooray.com"
WEB_ROOT="/var/www/personal"
BUILD_DIR="$HOME/personal"
DATA_DIR="$HOME/personal-data"
KEY_FILE="$HOME/.ssh/id_ed25519_personal"
REPO_URL="git@github.com:smsbotgefang95/personal.git"
NGINX_CONF="personal"
CURRENT_USER=$(logname || echo $USER)
VOCAB_API_PORT="8016"

echo "=================================================="
echo "🚀 Starting Isolated Multi-page Deployment for $DOMAIN"
echo "=================================================="

# 1. Handle SSH Key Isolation (Scoped to the entire 'personal' repo)
if [ ! -f "$KEY_FILE" ]; then
    echo "🔑 No dedicated key found. Generating a secure repository SSH key..."
    mkdir -p "$HOME/.ssh"
    ssh-keygen -t ed25519 -f "$KEY_FILE" -N "" -C "contabo-personal-apps"
    
    echo ""
    echo "⚠️  ACTION REQUIRED: Paste this public key into your GitHub repository deploy keys!"
    echo "👉 Go to: https://github.com/smsbotgefang95/personal/settings/keys"
    echo "👉 Click 'Add deploy key', name it 'Contabo Personal Repo Key', and paste the text below:"
    echo "----------------------------------------------------------------"
    cat "${KEY_FILE}.pub"
    echo "----------------------------------------------------------------"
    echo "Once you have added it to GitHub, run this script again to deploy!"
    exit 0
fi

# 2. Tell Git to explicitly use this specific key for the remaining operations
export GIT_SSH_COMMAND="ssh -i $KEY_FILE -o IdentitiesOnly=yes"

# 3. Fetch or pull the latest update from GitHub
if [ ! -d "$BUILD_DIR/.git" ]; then
    echo "📁 First time setup: Cloning repository from GitHub..."
    mkdir -p "$BUILD_DIR"
    git clone "$REPO_URL" "$BUILD_DIR"
else
    echo "🔄 Repository found. Pulling latest code changes..."
    cd "$BUILD_DIR"
    git pull
fi

# 4. Sync files to Nginx web root (cleanly excluding metadata)
echo "🧹 Cleaning and copying pages to web root..."
sudo mkdir -p "$WEB_ROOT"
sudo rsync -av --delete --exclude='.git*' --exclude='README.md' --exclude='deploy.sh' "$BUILD_DIR/" "$WEB_ROOT/"

echo "📚 Preparing shared vocabulary data..."
mkdir -p "$DATA_DIR"
if [ ! -f "$DATA_DIR/vocabulary-overrides.json" ]; then
    cp "$BUILD_DIR/data/vocabulary-overrides.json" "$DATA_DIR/vocabulary-overrides.json"
fi
if [ ! -f "$DATA_DIR/life-events.json" ]; then
    if [ -f "$BUILD_DIR/data/life-events.json" ]; then
        cp "$BUILD_DIR/data/life-events.json" "$DATA_DIR/life-events.json"
    else
        printf '{\n  "events": [],\n  "updatedAt": null\n}\n' > "$DATA_DIR/life-events.json"
    fi
fi
if [ ! -f "$DATA_DIR/time-entries.json" ]; then
    printf '{\n  "entries": [],\n  "activeEntry": null,\n  "updatedAt": null\n}\n' > "$DATA_DIR/time-entries.json"
fi
if [ ! -f "$DATA_DIR/question-progress.json" ]; then
    cat > "$DATA_DIR/question-progress.json" <<'EOF'
{
  "progress": {
    "1": "review",
    "27": "learned",
    "28": "learned",
    "42": "review",
    "50": "learning",
    "68": "tolearn",
    "69": "tolearn",
    "91": "tolearn",
    "92": "tolearn",
    "93": "tolearn",
    "99": "review"
  },
  "updatedAt": null
}
EOF
fi
if [ ! -f "$DATA_DIR/learning-english-custom.json" ]; then
    if [ -f "$BUILD_DIR/data/learning-english-custom.json" ]; then
        cp "$BUILD_DIR/data/learning-english-custom.json" "$DATA_DIR/learning-english-custom.json"
    else
        printf '{\n  "vocabulary": [],\n  "sentences": [],\n  "chunks": [],\n  "dialogues": [],\n  "updatedAt": null\n}\n' > "$DATA_DIR/learning-english-custom.json"
    fi
fi

if [ ! -f "$DATA_DIR/vocabulary-api.env" ]; then
    VOCAB_ADMIN_KEY=$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(24))
PY
)
    cat > "$DATA_DIR/vocabulary-api.env" <<EOF
VOCAB_API_HOST=127.0.0.1
VOCAB_API_PORT=$VOCAB_API_PORT
VOCAB_DATA_PATH=$DATA_DIR/vocabulary-overrides.json
VOCAB_PUBLIC_PATH=$WEB_ROOT/data/vocabulary-overrides.json
VOCAB_REPO_DIR=$BUILD_DIR
VOCAB_ADMIN_KEY=$VOCAB_ADMIN_KEY
LIFE_EVENTS_DATA_PATH=$DATA_DIR/life-events.json
LIFE_EVENTS_PUBLIC_PATH=$WEB_ROOT/data/life-events.json
LIFE_EVENTS_ADMIN_KEY=$VOCAB_ADMIN_KEY
TIME_ENTRIES_DATA_PATH=$DATA_DIR/time-entries.json
TIME_ENTRIES_ADMIN_KEY=$VOCAB_ADMIN_KEY
QUESTION_PROGRESS_DATA_PATH=$DATA_DIR/question-progress.json
LEARNING_ENGLISH_CUSTOM_DATA_PATH=$DATA_DIR/learning-english-custom.json
LEARNING_ENGLISH_CUSTOM_PUBLIC_PATH=$WEB_ROOT/data/learning-english-custom.json
LEARNING_ENGLISH_CUSTOM_ADMIN_KEY=$VOCAB_ADMIN_KEY
OPENAI_API_KEY=${OPENAI_API_KEY:-}
OPENAI_VOCAB_MODEL=${OPENAI_VOCAB_MODEL:-gpt-4o-mini}
VOCAB_GIT_SYNC=1
GIT_SSH_COMMAND="ssh -i $KEY_FILE -o IdentitiesOnly=yes"
EOF
    chmod 600 "$DATA_DIR/vocabulary-api.env"
    echo "Created vocabulary admin key at $DATA_DIR/vocabulary-api.env"
fi

if ! grep -q '^LIFE_EVENTS_DATA_PATH=' "$DATA_DIR/vocabulary-api.env"; then
    EXISTING_VOCAB_ADMIN_KEY=$(grep '^VOCAB_ADMIN_KEY=' "$DATA_DIR/vocabulary-api.env" | head -n 1 | cut -d= -f2-)
    cat >> "$DATA_DIR/vocabulary-api.env" <<EOF
LIFE_EVENTS_DATA_PATH=$DATA_DIR/life-events.json
LIFE_EVENTS_PUBLIC_PATH=$WEB_ROOT/data/life-events.json
LIFE_EVENTS_ADMIN_KEY=$EXISTING_VOCAB_ADMIN_KEY
EOF
    echo "Added Life Events API settings to $DATA_DIR/vocabulary-api.env"
fi

if ! grep -q '^TIME_ENTRIES_DATA_PATH=' "$DATA_DIR/vocabulary-api.env"; then
    EXISTING_VOCAB_ADMIN_KEY=$(grep '^VOCAB_ADMIN_KEY=' "$DATA_DIR/vocabulary-api.env" | head -n 1 | cut -d= -f2-)
    cat >> "$DATA_DIR/vocabulary-api.env" <<EOF
TIME_ENTRIES_DATA_PATH=$DATA_DIR/time-entries.json
TIME_ENTRIES_ADMIN_KEY=$EXISTING_VOCAB_ADMIN_KEY
EOF
    echo "Added Time Tracking API settings to $DATA_DIR/vocabulary-api.env"
fi

if ! grep -q '^QUESTION_PROGRESS_DATA_PATH=' "$DATA_DIR/vocabulary-api.env"; then
    cat >> "$DATA_DIR/vocabulary-api.env" <<EOF
QUESTION_PROGRESS_DATA_PATH=$DATA_DIR/question-progress.json
EOF
    echo "Added Citizenship Question Progress API settings to $DATA_DIR/vocabulary-api.env"
fi

if ! grep -q '^OPENAI_API_KEY=' "$DATA_DIR/vocabulary-api.env"; then
    cat >> "$DATA_DIR/vocabulary-api.env" <<EOF
OPENAI_API_KEY=${OPENAI_API_KEY:-}
OPENAI_VOCAB_MODEL=${OPENAI_VOCAB_MODEL:-gpt-4o-mini}
EOF
    echo "Added OpenAI vocabulary auto-fill settings to $DATA_DIR/vocabulary-api.env"
fi

if ! grep -q '^LEARNING_ENGLISH_CUSTOM_DATA_PATH=' "$DATA_DIR/vocabulary-api.env"; then
    EXISTING_VOCAB_ADMIN_KEY=$(grep '^VOCAB_ADMIN_KEY=' "$DATA_DIR/vocabulary-api.env" | head -n 1 | cut -d= -f2-)
    cat >> "$DATA_DIR/vocabulary-api.env" <<EOF
LEARNING_ENGLISH_CUSTOM_DATA_PATH=$DATA_DIR/learning-english-custom.json
LEARNING_ENGLISH_CUSTOM_PUBLIC_PATH=$WEB_ROOT/data/learning-english-custom.json
LEARNING_ENGLISH_CUSTOM_ADMIN_KEY=$EXISTING_VOCAB_ADMIN_KEY
EOF
    echo "Added Learning English custom content API settings to $DATA_DIR/vocabulary-api.env"
fi

if [ -n "${OPENAI_API_KEY:-}" ]; then
    python3 - "$DATA_DIR/vocabulary-api.env" "$OPENAI_API_KEY" "${OPENAI_VOCAB_MODEL:-gpt-4o-mini}" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
api_key = sys.argv[2]
model = sys.argv[3]
lines = path.read_text(encoding="utf-8").splitlines()
updates = {
    "OPENAI_API_KEY": api_key,
    "OPENAI_VOCAB_MODEL": model,
}
seen = set()
new_lines = []
for line in lines:
    key = line.split("=", 1)[0] if "=" in line else ""
    if key in updates:
        new_lines.append(f"{key}={updates[key]}")
        seen.add(key)
    else:
        new_lines.append(line)
for key, value in updates.items():
    if key not in seen:
        new_lines.append(f"{key}={value}")
path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
PY
    echo "Updated OpenAI vocabulary auto-fill key from deploy environment."
fi

echo "🧭 Ensuring vocabulary API restarts after server reboot..."
API_REBOOT_MARKER="# personal-vocabulary-api-reboot"
API_REBOOT_CMD="@reboot /bin/bash -lc 'DATA_DIR=\"$DATA_DIR\" BUILD_DIR=\"$BUILD_DIR\"; set -a; . \"\$DATA_DIR/vocabulary-api.env\"; set +a; nohup /usr/bin/python3 \"\$BUILD_DIR/server/vocabulary_api.py\" >> \"\$DATA_DIR/vocabulary-api.log\" 2>&1 & echo \$! > \"\$DATA_DIR/vocabulary-api.pid\"' $API_REBOOT_MARKER"
CRON_TMP=$(mktemp)
crontab -l 2>/dev/null | grep -vF "$API_REBOOT_MARKER" > "$CRON_TMP" || true
printf '%s\n' "$API_REBOOT_CMD" >> "$CRON_TMP"
crontab "$CRON_TMP"
rm -f "$CRON_TMP"

# 5. Apply standard directory permissions
echo "🔒 Adjusting folder permissions..."
sudo chown -R "$CURRENT_USER":"$CURRENT_USER" "$WEB_ROOT"
mkdir -p "$WEB_ROOT/data"
cp "$DATA_DIR/vocabulary-overrides.json" "$WEB_ROOT/data/vocabulary-overrides.json"
cp "$DATA_DIR/life-events.json" "$WEB_ROOT/data/life-events.json"
cp "$DATA_DIR/learning-english-custom.json" "$WEB_ROOT/data/learning-english-custom.json"
chmod 644 "$WEB_ROOT/data/vocabulary-overrides.json" "$WEB_ROOT/data/life-events.json" "$WEB_ROOT/data/learning-english-custom.json"

echo "🔁 Starting vocabulary API..."
if [ -f "$DATA_DIR/vocabulary-api.pid" ]; then
    OLD_PID=$(cat "$DATA_DIR/vocabulary-api.pid" || true)
    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        kill "$OLD_PID" || true
    fi
fi
set -a
. "$DATA_DIR/vocabulary-api.env"
set +a
nohup /usr/bin/python3 "$BUILD_DIR/server/vocabulary_api.py" >> "$DATA_DIR/vocabulary-api.log" 2>&1 &
echo $! > "$DATA_DIR/vocabulary-api.pid"
sleep 1
if ! kill -0 "$(cat "$DATA_DIR/vocabulary-api.pid")" 2>/dev/null; then
    echo "Vocabulary API failed to start. Recent log:"
    tail -n 40 "$DATA_DIR/vocabulary-api.log" || true
    exit 1
fi

# 6. Write/Verify the Nginx Configuration Block
echo "🌐 Ensuring Nginx server configuration is updated..."
sudo tee /etc/nginx/sites-available/$NGINX_CONF > /dev/null <<EOF
server {
    listen 80;
    server_name $DOMAIN;

    root $WEB_ROOT;
    index index.html;

    location / {
        try_files \$uri \$uri/ =404;
        expires -1;
        add_header Cache-Control "no-store, no-cache, must-revalidate, max-age=0";
    }

    location = /api/vocabulary-overrides {
        proxy_pass http://127.0.0.1:$VOCAB_API_PORT;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location = /api/life-events {
        proxy_pass http://127.0.0.1:$VOCAB_API_PORT;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location = /api/time-entries {
        client_max_body_size 16m;
        proxy_pass http://127.0.0.1:$VOCAB_API_PORT;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location = /api/learning-english/vocabulary-autofill {
        proxy_pass http://127.0.0.1:$VOCAB_API_PORT;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location = /api/learning-english/custom {
        proxy_pass http://127.0.0.1:$VOCAB_API_PORT;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location ^~ /api/citizenship/question-progress {
        proxy_pass http://127.0.0.1:$VOCAB_API_PORT;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location ~ /\. {
        deny all;
    }

    location ~* \.html\$ {
        expires -1;
        add_header Cache-Control "no-store, no-cache, must-revalidate, max-age=0";
    }

    location ~* \.(css|js|png|jpg|jpeg|gif|ico|svg)\$ {
        expires 1d;
        add_header Cache-Control "public, no-transform";
    }
}
EOF

# 7. Activate the configuration block if not already linked
if [ ! -f "/etc/nginx/sites-enabled/$NGINX_CONF" ]; then
    sudo ln -s /etc/nginx/sites-available/$NGINX_CONF /etc/nginx/sites-enabled/
fi

# 8. Safety check Nginx syntax and reload the server configuration
echo "🧪 Testing Nginx configuration rules..."
sudo nginx -t

echo "🔄 Reloading Nginx safely..."
sudo systemctl reload nginx

# 9. Secure with SSL via Certbot
echo "🔒 Confirming SSL status via Certbot..."
sudo certbot --nginx -d "$DOMAIN" --keep-until-expiring --non-interactive --agree-tos --register-unsafely-without-email

# Certbot can rewrite the active server block. Re-apply API upload limits after
# its nginx installer runs so Time Analysis sync accepts the intended payload size.
echo "📦 Ensuring Time Analysis API upload limit is active..."
TMP_NGINX_CONF=$(mktemp)
python3 - "/etc/nginx/sites-available/$NGINX_CONF" > "$TMP_NGINX_CONF" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()
needle = "    location = /api/time-entries {\n"
directive = "        client_max_body_size 16m;\n"
if needle not in text:
    raise SystemExit("missing /api/time-entries nginx location")
location_start = text.index(needle)
location_end = text.index("    }\n", location_start)
location_block = text[location_start:location_end]
if directive not in location_block:
    text = text[:location_start + len(needle)] + directive + text[location_start + len(needle):]
print(text, end="")
PY
sudo tee "/etc/nginx/sites-available/$NGINX_CONF" > /dev/null < "$TMP_NGINX_CONF"
rm -f "$TMP_NGINX_CONF"

sudo nginx -t
sudo systemctl reload nginx

echo "=================================================="
echo "🎉 Success! Your multi-page site is live at: https://$DOMAIN"
echo "=================================================="
