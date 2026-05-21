#!/bin/bash

# Exit immediately if any command fails
set -e

# --- Configuration Variables ---
DOMAIN="personal.homehomehooray.com"
WEB_ROOT="/var/www/personal"
BUILD_DIR="$HOME/personal"
KEY_FILE="$HOME/.ssh/id_ed25519_personal"
REPO_URL="git@github.com:smsbotgefang95/personal.git"
NGINX_CONF="personal"
CURRENT_USER=$(logname || echo $USER)

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

# 5. Apply standard directory permissions
echo "🔒 Adjusting folder permissions..."
sudo chown -R "$CURRENT_USER":"$CURRENT_USER" "$WEB_ROOT"

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
sudo certbot --nginx -d "$DOMAIN" --keep-until-expiring --non-interactive --agree-tos --register-unsafely-without-email || true

echo "=================================================="
echo "🎉 Success! Your multi-page site is live at: https://$DOMAIN"
echo "=================================================="
