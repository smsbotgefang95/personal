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

# 5. Apply standard directory permissions
echo "🔒 Adjusting folder permissions..."
sudo chown -R "$CURRENT_USER":"$CURRENT_USER" "$WEB_ROOT"
mkdir -p "$WEB_ROOT/data"
cp "$DATA_DIR/vocabulary-overrides.json" "$WEB_ROOT/data/vocabulary-overrides.json"
cp "$DATA_DIR/life-events.json" "$WEB_ROOT/data/life-events.json"

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

echo "=================================================="
echo "🎉 Success! Your multi-page site is live at: https://$DOMAIN"
echo "=================================================="
