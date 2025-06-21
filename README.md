# Spidertise Auto Forwarder Bot

A powerful Telegram bot for automatic message forwarding, auto-reply, and user management with a secure web interface.

## Features

- 🤖 **Telegram Bot Integration**: Full-featured bot with command handlers
- 🌐 **Secure Web Interface**: FastAPI-powered web app with HTTPS support
- 🔄 **Auto Forwarding**: Automated message forwarding to multiple groups
- 💬 **Auto Reply**: Intelligent keyword-based auto responses
- 👥 **User Management**: Subscription-based user access control
- 🔒 **SSL/HTTPS**: Production-ready security with Let's Encrypt
- 📊 **Analytics**: Message forwarding statistics and tracking
- 🛡️ **Anti-Delete**: Monitor and backup deleted messages

## Prerequisites

- Ubuntu/Debian VPS with root access
- Python 3.8 or higher
- Domain name (we'll use DuckDNS for free)
- Telegram Bot Token
- Telegram API credentials

## Installation Guide

### Step 1: Server Setup


# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install python3 python3-pip python3-venv nginx certbot python3-certbot-nginx git -y

# Create application directory
sudo mkdir -p /opt/spidertise
sudo chown $USER:$USER /opt/spidertise
cd /opt/spidertise


### Step 2: Clone and Setup Application

# Clone your repository (replace with your repo URL)
git clone https://github.com/yourusername/spidertise-bot.git .

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt


### Step 3: DuckDNS Domain Setup
Get DuckDNS Domain:

1. Visit DuckDNS.org
2. Sign in with your preferred method
3. Create a new domain (e.g., yourbot.duckdns.org)
4. Note your DuckDNS token

Configure DuckDNS Auto-Update:


# Create DuckDNS update script
sudo nano /opt/spidertise/duckdns_update.sh


Add this content:


#!/bin/bash
# DuckDNS Update Script
DOMAIN="yourbot"  # Your DuckDNS subdomain (without .duckdns.org)
TOKEN="your-duckdns-token"  # Your DuckDNS token

# Get current public IP
CURRENT_IP=$(curl -s https://api.ipify.org)

# Update DuckDNS
curl -s "https://www.duckdns.org/update?domains=${DOMAIN}&token=${TOKEN}&ip=${CURRENT_IP}"

echo "$(date): Updated ${DOMAIN}.duckdns.org to ${CURRENT_IP}"



# Make script executable
chmod +x /opt/spidertise/duckdns_update.sh

# Test the script
./duckdns_update.sh

# Add to crontab for automatic updates every 5 minutes
crontab -e
# Add this line:
*/5 * * * * /opt/spidertise/duckdns_update.sh >> /var/log/duckdns.log 2>&1


### Step 4: Environment Configuration

# Copy environment template
cp .env.example .env

# Edit environment variables
nano .env


Configure your .env file:


# Bot Configuration
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ
ADMIN_IDS=123456789,987654321
ADMIN_USERNAME=youradminusername

# Web App Configuration
WEBAPP=https://yourbot.duckdns.org
SECRET_KEY=your-super-secret-key-here
HOST=0.0.0.0
PORT=8000

# DuckDNS Configuration
DUCKDNS_DOMAIN=yourbot.duckdns.org
DUCKDNS_TOKEN=your-duckdns-token

# SSL Configuration (will be updated after certbot)
SSL_KEYFILE=/etc/letsencrypt/live/yourbot.duckdns.org/privkey.pem
SSL_CERTFILE=/etc/letsencrypt/live/yourbot.duckdns.org/fullchain.pem


### Step 5: Nginx Configuration

# Create Nginx configuration
sudo nano /etc/nginx/sites-available/spidertise


Add this configuration:


server {
    listen 80;
    server_name yourbot.duckdns.org;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourbot.duckdns.org;
    
    # SSL Configuration (will be added by certbot)
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    
    # Proxy to FastAPI application
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;
        
        # WebSocket support (if needed)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # Static files (if any)
    location /static/ {
        alias /opt/spidertise/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}



# Enable the site
sudo ln -s /etc/nginx/sites-available/spidertise /etc/nginx/sites-enabled/

# Remove default site
sudo rm /etc/nginx/sites-enabled/default

# Test Nginx configuration
sudo nginx -t

# Start and enable Nginx
sudo systemctl start nginx
sudo systemctl enable nginx


### Step 6: SSL Certificate with Let's Encrypt

# Stop nginx temporarily
sudo systemctl stop nginx

# Obtain SSL certificate
sudo certbot certonly --standalone -d yourbot.duckdns.org

# Start nginx
sudo systemctl start nginx

# Configure automatic renewal
sudo certbot renew --dry-run

# Add renewal to crontab
sudo crontab -e
# Add this line:
0 12 * * * /usr/bin/certbot renew --quiet --reload-nginx


### Step 7: Create Systemd Service

# Create systemd service file
sudo nano /etc/systemd/system/spidertise.service


Add this content:


[Unit]
Description=Spidertise Auto Forwarder Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/spidertise
Environment=PATH=/opt/spidertise/venv/bin
ExecStart=/opt/spidertise/venv/bin/python main.py
Restart=always
RestartSec=10

# Environment variables
EnvironmentFile=/opt/spidertise/.env

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/spidertise

[Install]
WantedBy=multi-user.target



# Reload systemd and start service
sudo systemctl daemon-reload
sudo systemctl enable spidertise
sudo systemctl start spidertise

# Check service status
sudo systemctl status spidertise


### Step 8: Firewall Configuration

# Configure UFW firewall
sudo ufw allow ssh
sudo ufw allow 'Nginx Full'
sudo ufw --force enable

# Check firewall status
sudo ufw status