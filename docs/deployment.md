# DC-ShiftMaster Pro — Deployment Guide

## Quick Start (Docker)

```bash
# 1. Build the image
docker build -t shiftmaster .

# 2. Create a data directory for the SQLite database
mkdir -p /opt/shiftmaster/data

# 3. Run the container
docker run -d \
  --name shiftmaster \
  -p 5000:5000 \
  -v /opt/shiftmaster/data:/data \
  -e SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')" \
  -e SHIFTMASTER_PASSWORD="your-team-password" \
  shiftmaster
```

The app is now available at `http://<your-server-ip>:5000`.

## Environment Variables

See `.env.example` for the full list. Key variables:

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | *(random each restart)* | Flask session signing key — set for persistent sessions |
| `SHIFTMASTER_HOST` | `0.0.0.0` | Bind address |
| `SHIFTMASTER_PORT` | `5000` | Bind port |
| `SHIFTMASTER_DB_PATH` | `/data/teammates.db` | SQLite database path |
| `SHIFTMASTER_PASSWORD` | `shiftmaster` | Shared team password |

## Running Without Docker

```bash
pip install -r requirements-html.txt
pip install -e .
gunicorn -c gunicorn.conf.py
```

---

## TLS Termination

Production deployments should serve traffic over HTTPS. Two common approaches:

### Option A: Nginx Reverse Proxy

Install Nginx on the same host (or a separate proxy host) and terminate TLS there.

Sample Nginx configuration (`/etc/nginx/sites-available/shiftmaster`):

```nginx
upstream shiftmaster {
    server 127.0.0.1:5000;
}

server {
    listen 80;
    server_name shiftmaster.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name shiftmaster.example.com;

    ssl_certificate     /etc/letsencrypt/live/shiftmaster.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/shiftmaster.example.com/privkey.pem;

    # Modern TLS settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;

    location / {
        proxy_pass http://shiftmaster;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket support — required for real-time notifications
    location /ws/ {
        proxy_pass http://shiftmaster;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 86400;  # keep WebSocket connections alive
    }
}
```

To obtain a free TLS certificate with Let's Encrypt:

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d shiftmaster.example.com
```

### Option B: AWS Application Load Balancer

If running on EC2, you can use an ALB for TLS termination instead of Nginx:

1. Create an ACM certificate for your domain in the AWS Console
2. Create a Target Group pointing to your EC2 instance on port 5000 (HTTP)
3. Create an Application Load Balancer with:
   - HTTPS listener on port 443 using the ACM certificate
   - Forward to the Target Group
4. Enable sticky sessions on the Target Group (required for session cookies)
5. Configure the health check path to `/health`

The ALB handles WebSocket upgrades automatically — no special configuration needed.

With ALB, your EC2 security group only needs to allow traffic from the ALB (no direct public access on port 5000).

---

## Health Check

The app exposes `GET /health` (no auth required) for load balancer and monitoring use:

- `200 {"status": "healthy"}` — app and database are operational
- `503 {"status": "unhealthy", "reason": "database unavailable"}` — database connection failed

## Database Backups

The SQLite database lives at the path specified by `SHIFTMASTER_DB_PATH`. Back it up regularly:

```bash
# Simple file copy (safe because SQLite uses WAL mode)
cp /opt/shiftmaster/data/teammates.db /opt/shiftmaster/backups/teammates-$(date +%F).db
```
