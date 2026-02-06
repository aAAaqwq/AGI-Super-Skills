# Nginx HTTPS Configuration

## Problem

Docker-deployed Nginx only listens on port 80 (HTTP). When Cloudflare force HTTPS is enabled, the site becomes inaccessible because the origin doesn't support HTTPS.

## Root Cause

Nginx configuration only has `listen 80;` without `listen 443 ssl;`

## Solution

### 1. Obtain SSL Certificate

For Cloudflare: Use **Origin Server Certificate**

1. Cloudflare Dashboard → SSL/TLS → Origin Server
2. Create Certificate (15 years validity recommended)
3. Save as `nginx.crt` (certificate) and `nginx.key` (private key)

### 2. Configure nginx.conf

```nginx
# HTTP (80) - Redirect to HTTPS
server {
    listen 80;
    server_name localhost;
    return 301 https://$host$request_uri;
}

# HTTPS (443)
server {
    listen 443 ssl;
    server_name localhost;

    ssl_certificate /etc/nginx/ssl/nginx.crt;
    ssl_certificate_key /etc/nginx/ssl/nginx.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # ... rest of your config
}
```

### 3. Update docker-compose.yml

```yaml
services:
  frontend:
    ports:
      - "5668:80"
      - "5669:443"    # Map HTTPS port
    volumes:
      - ./certificates:/etc/nginx/ssl:ro   # Mount certificates
```

### 4. Certificate Directory Structure

```
project/
├── docker-compose.yml
├── certificates/
│   ├── nginx.crt   # SSL certificate
│   └── nginx.key   # Private key
```

## Verification

```bash
# Test HTTPS locally
curl -k https://localhost:5669

# Test HTTP redirect
curl -I http://localhost:5668
# Should return: HTTP/1.1 301 Moved Permanently
```

## Cloudflare Tunnel Configuration

Update Tunnel service to use HTTPS:

```
Service: https://localhost:5669
```

Or for container-to-container:

```
Service: https://container-name:443
```
