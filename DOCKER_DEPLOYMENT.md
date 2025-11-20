# Docker Deployment Guide for Open LPR

This guide provides comprehensive instructions for deploying the Open LPR application using Docker and Docker Compose.

## Overview

The Docker deployment includes:
- Multi-stage optimized Dockerfile for production
- Volume persistence for SQLite database and media files
- Environment variable configuration
- Health checks and monitoring
- Gunicorn WSGI server for production performance (included in requirements.txt)

## Prerequisites

- Docker 20.10+ installed
- Docker Compose 2.0+ installed
- Sufficient disk space for media files and database
- Qwen3-VL API access (API key and endpoint)

## Quick Start

### 1. Environment Configuration

Create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
```

Edit the `.env` file with your configuration:

```env
# Django Settings
SECRET_KEY=your-very-secret-key-here
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1,your-domain.com

# Qwen3-VL API Configuration
QWEN_API_KEY=your-qwen-api-key
QWEN_BASE_URL=https://your-open-api-compatible-endpoint.com/v1
QWEN_MODEL=qwen3-vl-4b-instruct

# File Upload Settings
UPLOAD_FILE_MAX_SIZE=10485760  # 10MB
MAX_BATCH_SIZE=10

# Optional: Create superuser automatically
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_EMAIL=admin@example.com
DJANGO_SUPERUSER_PASSWORD=your-secure-password
```

### 2. Run with Docker Compose

```bash
# Pull and start the application using published image
docker-compose up -d

# View logs
docker-compose logs -f

# Check container status
docker-compose ps
```

**Note**: This uses the pre-built image `ghcr.io/faisalthaheem/open-lpr:latest` instead of building locally.

### 3. Access the Application

The application will be available at:
- Web Interface: http://localhost:8000
- API Endpoint: http://localhost:8000/api/v1/
- Health Check: http://localhost:8000/health/

## Volume Structure

The Docker setup uses the following volume mounts:

```
./container-data/ → /app/data/          (SQLite database)
./container-media/→ /app/media/         (Uploaded and processed images)
./staticfiles/   → /app/staticfiles/   (Collected static files)
```

### Database Persistence

The SQLite database location is controlled by the `DATABASE_PATH` environment variable:

- **Default (Development)**: `./data/db.sqlite3` (project root/data/)
- **Docker**: `/app/data/db.sqlite3` (mounted to host ./container-data/)

This approach ensures:
- Database persistence across container restarts
- Easy backup and migration
- Direct access to the database file for maintenance
- Proper volume mounting for containerized deployment
- No permission issues in development environment

### Environment Configuration

The application automatically detects the environment and configures paths accordingly:

#### Development Environment (default):
- Database: `./data/db.sqlite3`
- Logs: `./data/django.log`
- Media: `./media/`
- Static files: Automatically created in `lpr_app/static/` if missing

#### Docker Environment:
- Database: `/app/data/db.sqlite3` (mounted to host ./container-data/)
- Logs: `/app/data/django.log` (mounted to host ./container-data/)
- Media: `/app/media/` (mounted to host ./container-media/)

### Media Files Persistence

All uploaded and processed images are stored in `./container-media/` on the host:
- Original images: `./container-media/uploads/`
- Processed images: `./container-media/processed/`

## Production Deployment

### 1. Security Considerations

For production deployment:

1. **Change default secrets**:
   ```env
   SECRET_KEY=generate-a-strong-random-key
   DJANGO_SUPERUSER_PASSWORD=use-a-strong-password
   ```

2. **Set DEBUG to False**:
   ```env
   DEBUG=False
   ```

3. **Configure ALLOWED_HOSTS**:
   ```env
   ALLOWED_HOSTS=your-domain.com,www.your-domain.com
   ```

4. **Use HTTPS** in production (configure reverse proxy like Nginx)

### 2. Performance Optimization

The Dockerfile is optimized for production with:
- Multi-stage build for smaller image size
- Non-root user for security
- Gunicorn WSGI server with 3 workers
- 120-second timeout for image processing

### 3. Scaling

For higher traffic, you can scale the application:

```bash
# Scale to 3 instances
docker-compose up -d --scale lpr-app=3
```

Note: When scaling, consider:
- Using a shared database (PostgreSQL instead of SQLite)
- Shared storage for media files (NFS, S3, etc.)
- Load balancer for distributing traffic

## Docker Commands Reference

### Building and Running

```bash
# Build the image
docker build -t open-lpr:latest .

# Run with volume mounts
docker run -d \
  --name open-lpr \
  -p 8000:8000 \
  -v $(pwd)/container-data:/app/data \
  -v $(pwd)/container-media:/app/media \
  --env-file .env \
  open-lpr:latest
```

### Maintenance

```bash
# View logs
docker-compose logs -f lpr-app

# Execute commands in container
docker-compose exec lpr-app bash

# Create Django superuser manually
docker-compose exec lpr-app python manage.py createsuperuser

# Run migrations
docker-compose exec lpr-app python manage.py migrate

# Collect static files
docker-compose exec lpr-app python manage.py collectstatic --noinput
```

### Backup and Restore

```bash
# Backup database
docker-compose exec lpr-app cp /app/data/db.sqlite3 /app/data/db.sqlite3.backup

# Restore database
docker-compose exec lpr-app cp /app/data/db.sqlite3.backup /app/data/db.sqlite3

# Backup media files
tar -czf container-media-backup-$(date +%Y%m%d).tar.gz container-media/
```

## Troubleshooting

### Common Issues

1. **Container fails to start**:
   ```bash
   # Check logs
   docker-compose logs lpr-app
   
   # Check configuration
   docker-compose config
   ```

2. **Database errors**:
   ```bash
   # Check database permissions
   ls -la container-data/
   
   # Run migrations manually
   docker-compose exec lpr-app python manage.py migrate
   ```

3. **Permission issues**:
   ```bash
   # Fix volume permissions
   sudo chown -R $USER:$USER container-data/ container-media/
   ```

4. **API connection issues**:
   - Verify QWEN_API_KEY in .env file
   - Check QWEN_BASE_URL accessibility
   - Review application logs for API errors

### Health Checks

The container includes health checks:
```bash
# Check health status
docker-compose ps

# Manual health check
curl http://localhost:8000/health/
```

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| SECRET_KEY | django-insecure-change-me | Django secret key |
| DEBUG | False | Django debug mode |
| ALLOWED_HOSTS | localhost,127.0.0.1 | Allowed hosts for Django |
| QWEN_API_KEY | - | Qwen3-VL API key (required) |
| QWEN_BASE_URL | https://ollama.computedsynergy.com/compatible-mode/v1 | API endpoint URL |
| QWEN_MODEL | qwen3-vl | AI model name |
| UPLOAD_FILE_MAX_SIZE | 10485760 | Maximum upload size (10MB) |
| MAX_BATCH_SIZE | 10 | Maximum batch processing size |
| DJANGO_SUPERUSER_USERNAME | - | Auto-create superuser username |
| DJANGO_SUPERUSER_EMAIL | - | Auto-create superuser email |
| DJANGO_SUPERUSER_PASSWORD | - | Auto-create superuser password |

## Advanced Configuration

### Custom Gunicorn Settings

To customize Gunicorn settings, modify the command in docker-compose.yml:

```yaml
command: ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--worker-class", "gevent", "--timeout", "180", "lpr_project.wsgi:application"]
```

### Using External Database

For production, consider using PostgreSQL:

1. Add PostgreSQL service to docker-compose.yml
2. Update DATABASE_URL environment variable
3. Install psycopg2 in requirements.txt

### Reverse Proxy Configuration

For production deployment with Nginx:

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location /static/ {
        alias /path/to/staticfiles/;
    }
    
    location /media/ {
        alias /path/to/media/;
    }
}
```

## Support

For issues related to:
- Docker deployment: Check this guide and Docker documentation
- Application functionality: Review the main README.md
- API issues: Check API_DOCUMENTATION.md

For additional help, create an issue in the project repository with:
- Docker version
- Docker Compose version
- Complete error logs
- Environment configuration (without sensitive data)