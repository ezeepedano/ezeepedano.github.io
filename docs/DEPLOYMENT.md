# ERP System - Deployment Guide

## Table of Contents

- [Prerequisites](#prerequisites)
- [Development Deployment](#development-deployment)
- [Production Deployment](#production-deployment)
- [Docker Deployment](#docker-deployment)
- [Cloud Deployment](#cloud-deployment)
- [Database Migration](#database-migration)
- [Static Files](#static-files)
- [SSL/HTTPS Setup](#sslhttps-setup)
- [Monitoring & Logging](#monitoring--logging)
- [Backup & Recovery](#backup--recovery)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements

**Minimum**:
- CPU: 2 cores
- RAM: 4GB
- Storage: 20GB SSD
- OS: Ubuntu 20.04+ / Debian 11+ / RHEL 8+

**Recommended (Production)**:
- CPU: 4+ cores
- RAM: 8GB+
- Storage: 50GB+ SSD
- OS: Ubuntu 22.04 LTS

### Software Requirements

- Python 3.13+
- PostgreSQL 14+
- Redis 7+
- Nginx 1.20+
- Git

---

## Development Deployment

### Local Setup

```bash
# 1. Clone repository
git clone https://github.com/your-org/erp-system.git
cd erp-system

# 2. Create virtual environment
python3.13 -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create .env file
cp .env.example .env
# Edit .env with your settings

# 5. Run migrations
python manage.py migrate

# 6. Create superuser
python manage.py createsuperuser

# 7. Collect static files
python manage.py collectstatic --noinput

# 8. Run development server
python manage.py runserver
```

Access at: `http://localhost:8000`

---

## Production Deployment

### Manual Production Setup (Ubuntu 22.04)

#### 1. System Preparation

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3.13 python3.13-venv python3.13-dev \
    postgresql-14 postgresql-contrib \
    redis-server \
    nginx \
    git \
    supervisor \
    certbot python3-certbot-nginx

# Create app user
sudo useradd -m -s /bin/bash erp
sudo su - erp
```

#### 2. Application Setup

```bash
# Clone repository
git clone https://github.com/your-org/erp-system.git /home/erp/app
cd /home/erp/app

# Create virtual environment
python3.13 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install gunicorn psycopg2-binary

# Create directories
mkdir -p logs static media backups
```

#### 3. Database Setup

```bash
# Switch to postgres user
sudo su - postgres

# Create database and user
psql
```

```sql
CREATE DATABASE erp_production;
CREATE USER erp_user WITH PASSWORD 'secure_password_here';
ALTER ROLE erp_user SET client_encoding TO 'utf8';
ALTER ROLE erp_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE erp_user SET timezone TO 'America/Argentina/Buenos_Aires';
GRANT ALL PRIVILEGES ON DATABASE erp_production TO erp_user;
\q
```

#### 4. Environment Configuration

```bash
# Edit .env
nano /home/erp/app/.env
```

```bash
# Production settings
DEBUG=False
SECRET_KEY=generate-a-strong-secret-key-here
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database
DATABASE_URL=postgresql://erp_user:secure_password_here@localhost:5432/erp_production

# Redis
REDIS_URL=redis://localhost:6379/0

# Email
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

# Security
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

#### 5. Run Migrations

```bash
source /home/erp/app/venv/bin/activate
cd /home/erp/app
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

#### 6. Gunicorn Configuration

Create `/home/erp/app/gunicorn_config.py`:

```python
"""Gunicorn configuration for production."""
import multiprocessing

# Server socket
bind = "0.0.0.0:8000"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "gthread"
threads = 2
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
timeout = 30
keepalive = 2

# Logging
accesslog = "/home/erp/app/logs/gunicorn-access.log"
errorlog = "/home/erp/app/logs/gunicorn-error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "erp_gunicorn"

# Server mechanics
daemon = False
pidfile = "/home/erp/app/logs/gunicorn.pid"
user = "erp"
group = "erp"
tmp_upload_dir = None

# Security
limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8190
```

#### 7. Supervisor Configuration

Create `/etc/supervisor/conf.d/erp.conf`:

```ini
[program:erp]
directory=/home/erp/app
command=/home/erp/app/venv/bin/gunicorn core_erp.wsgi:application -c gunicorn_config.py
user=erp
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/home/erp/app/logs/supervisor.log
environment=PATH="/home/erp/app/venv/bin"
```

```bash
# Reload supervisor
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start erp
sudo supervisorctl status
```

#### 8. Nginx Configuration

Create `/etc/nginx/sites-available/erp`:

```nginx
upstream erp_app {
    server 127.0.0.1:8000 fail_timeout=0;
}

server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;
    
    # SSL Configuration (will be added by certbot)
    
    client_max_body_size 100M;
    
    # Logging
    access_log /var/log/nginx/erp-access.log;
    error_log /var/log/nginx/erp-error.log;
    
    # Security headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    
    # Static files
    location /static/ {
        alias /home/erp/app/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    
    # Media files
    location /media/ {
        alias /home/erp/app/media/;
        expires 7d;
    }
    
    # Application
    location / {
        proxy_pass http://erp_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/erp /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

#### 9. SSL Certificate (Let's Encrypt)

```bash
# Obtain certificate
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Auto-renewal (already configured)
sudo certbot renew --dry-run
```

---

## Docker Deployment

### Using Docker Compose

```bash
# 1. Clone repository
git clone https://github.com/your-org/erp-system.git
cd erp-system

# 2. Create .env file
cp .env.example .env
# Edit .env with production settings

# 3. Build and start services
docker-compose up -d

# 4. Run migrations
docker-compose exec web python manage.py migrate

# 5. Create superuser
docker-compose exec web python manage.py createsuperuser

# 6. Collect static files
docker-compose exec web python manage.py collectstatic --noinput
```

### View logs

```bash
docker-compose logs -f web
```

### Stop services

```bash
docker-compose down
```

---

## Cloud Deployment

### AWS Deployment (EC2 + RDS + ElastiCache)

#### 1. Infrastructure Setup

**EC2 Instance**:
- Type: t3.medium (2 vCPU, 4GB RAM)
- OS: Ubuntu 22.04 LTS
- Security Group: Allow 80, 443, 22

**RDS PostgreSQL**:
- Instance: db.t3.micro
- Engine: PostgreSQL 14
- Multi-AZ: Yes (production)
- Automated backups: 7 days

**ElastiCache Redis**:
- Node type: cache.t3.micro
- Engine: Redis 7.x

#### 2. Application Deployment

```bash
# SSH to EC2
ssh -i your-key.pem ubuntu@your-ec2-ip

# Follow manual production setup steps
# Use RDS and ElastiCache endpoints in .env
```

#### 3. Load Balancer Setup

- Create Application Load Balancer
- Configure target group (EC2 instances)
- Add SSL certificate (ACM)
- Configure health checks: `/health/`

### DigitalOcean Deployment (Droplet + Managed DB)

Similar to AWS but using:
- Droplet (4GB RAM recommended)
- Managed PostgreSQL Database
- Managed Redis

### Heroku Deployment

```bash
# 1. Install Heroku CLI
curl https://cli-assets.heroku.com/install.sh | sh

# 2. Login
heroku login

# 3. Create app
heroku create erp-production

# 4. Add addons
heroku addons:create heroku-postgresql:standard-0
heroku addons:create heroku-redis:premium-0

# 5. Set config vars
heroku config:set SECRET_KEY=your-secret-key
heroku config:set DEBUG=False
heroku config:set ALLOWED_HOSTS=erp-production.herokuapp.com

# 6. Deploy
git push heroku main

# 7. Run migrations
heroku run python manage.py migrate

# 8. Create superuser
heroku run python manage.py createsuperuser
```

---

## Database Migration

### From SQLite to PostgreSQL

```bash
# 1. Dump SQLite data
python manage.py dumpdata --natural-foreign --natural-primary \
    --exclude=contenttypes --exclude=auth.permission \
    --indent=2 > backup.json

# 2. Update DATABASE_URL in .env to PostgreSQL

# 3. Run migrations
python manage.py migrate

# 4. Load data
python manage.py loaddata backup.json
```

---

## Static Files

### S3/CloudFront Setup

Install django-storages:

```bash
pip install django-storages boto3
```

Update `settings.py`:

```python
# S3 Configuration
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME')
AWS_S3_REGION_NAME = 'us-east-1'

# Static files
STATICFILES_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
```

---

## SSL/HTTPS Setup

### Let's Encrypt (Certbot)

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d yourdomain.com

# Auto-renewal
sudo systemctl status certbot.timer
```

### Custom SSL Certificate

```nginx
server {
    listen 443 ssl http2;
    
    ssl_certificate /etc/ssl/certs/your-cert.crt;
    ssl_certificate_key /etc/ssl/private/your-key.key;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    
    # ... rest of config
}
```

---

## Monitoring & Logging

### Sentry Setup

```bash
pip install sentry-sdk
```

Update `settings.py`:

```python
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

sentry_sdk.init(
    dsn=os.getenv('SENTRY_DSN'),
    integrations=[DjangoIntegration()],
    traces_sample_rate=0.1,
    send_default_pii=True,
    environment=os.getenv('ENVIRONMENT', 'production')
)
```

### Application Logs

```python
# settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/home/erp/app/logs/django.log',
            'maxBytes': 1024 * 1024 * 15,  # 15MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
```

---

## Backup & Recovery

### Automatic Database Backups

Create `/home/erp/scripts/backup.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/home/erp/backups"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="erp_production"
DB_USER="erp_user"

# Create backup
pg_dump -U $DB_USER $DB_NAME | gzip > $BACKUP_DIR/db_$DATE.sql.gz

# Keep only last 30 days
find $BACKUP_DIR -name "db_*.sql.gz" -mtime +30 -delete
```

Add to crontab:

```bash
# Daily backup at 2 AM
0 2 * * * /home/erp/scripts/backup.sh
```

### Restore from Backup

```bash
gunzip < backup.sql.gz | psql -U erp_user erp_production
```

---

## Troubleshooting

### Common Issues

**1. Permission Errors**

```bash
sudo chown -R erp:erp /home/erp/app
chmod -R 755 /home/erp/app
```

**2. Static Files Not Loading**

```bash
python manage.py collectstatic --noinput
sudo systemctl restart nginx
```

**3. Database Connection Errors**

Check PostgreSQL is running:

```bash
sudo systemctl status postgresql
```

Test connection:

```bash
psql -U erp_user -d erp_production -h localhost
```

**4. Application Not Starting**

Check logs:

```bash
tail -f /home/erp/app/logs/gunicorn-error.log
sudo supervisorctl tail -f erp
```

**5. High Memory Usage**

Reduce Gunicorn workers:

```python
# gunicorn_config.py
workers = 2  # Reduce from auto-calculated value
```

---

## Performance Tuning

### PostgreSQL Optimization

Edit `/etc/postgresql/14/main/postgresql.conf`:

```
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 6MB
min_wal_size = 1GB
max_wal_size = 4GB
```

```bash
sudo systemctl restart postgresql
```

### Redis Optimization

Edit `/etc/redis/redis.conf`:

```
maxmemory 256mb
maxmemory-policy allkeys-lru
```

---

## Security Checklist

- [ ] DEBUG=False in production
- [ ] Strong SECRET_KEY
- [ ] HTTPS enabled
- [ ] Security headers configured
- [ ] Database credentials secured
- [ ] Firewall configured (UFW/Security Groups)
- [ ] Regular security updates
- [ ] Backups automated
- [ ] Monitoring enabled (Sentry)
- [ ] Rate limiting configured

---

**Deployment Complete!** 🚀

For support: support@erp-system.com
