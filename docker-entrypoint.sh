#!/bin/bash
set -e

echo "Starting Open LPR application initialization..."

# Wait for database to be available (if using external database)
# For SQLite, this is not needed but keeping for future compatibility

# Check if the database directory exists
if [ ! -d "/app/data" ]; then
    echo "Creating data directory for SQLite database..."
    mkdir -p /app/data
fi

# Ensure proper permissions for data directory
# Run as root to set permissions, then switch back
if [ "$(id -u)" = "0" ]; then
    chown -R django:django /app/data
    chmod -R 755 /app/data
else
    echo "Warning: Running as non-root, may not be able to set permissions"
fi

# Check if the media directory exists
if [ ! -d "/app/media" ]; then
    echo "Creating media directory for uploaded files..."
    mkdir -p /app/media
fi

# Ensure proper permissions for media directory
# Run as root to set permissions, then switch back
if [ "$(id -u)" = "0" ]; then
    chown -R django:django /app/media
    chmod -R 755 /app/media
else
    echo "Warning: Running as non-root, may not be able to set media permissions"
fi

# Change to app directory
cd /app

# Create a simple log file to ensure it exists and has right permissions
touch /app/data/django.log 2>/dev/null || true
if [ "$(id -u)" = "0" ]; then
    chown django:django /app/data/django.log
    chmod 644 /app/data/django.log
fi

# Ensure database file has correct ownership if it exists
# Get the database path from Django settings or use default
DB_PATH="${DATABASE_PATH:-/app/db.sqlite3}"
if [ -f "$DB_PATH" ]; then
    echo "Setting ownership for database file: $DB_PATH"
    if [ "$(id -u)" = "0" ]; then
        chown django:django "$DB_PATH"
        chmod 644 "$DB_PATH"
    fi
else
    echo "Database file not found at $DB_PATH, will be created by Django migrations"
fi

# Run database migrations
echo "Running database migrations..."
python manage.py migrate --noinput

# Ensure database file has correct ownership after migrations
# This handles the case where the database was created during migrations
if [ -f "$DB_PATH" ]; then
    echo "Setting ownership for database file after migrations: $DB_PATH"
    if [ "$(id -u)" = "0" ]; then
        chown django:django "$DB_PATH"
        chmod 644 "$DB_PATH"
    fi
fi

# Collect static files (in case they weren't collected during build)
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Create superuser if environment variables are provided
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_EMAIL" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    echo "Creating superuser..."
    python manage.py createsuperuser --noinput --username "$DJANGO_SUPERUSER_USERNAME" --email "$DJANGO_SUPERUSER_EMAIL" || echo "Superuser already exists or creation failed"
fi

echo "Initialization complete. Starting application..."

# If running as root, switch to django user for the actual application
if [ "$(id -u)" = "0" ]; then
    echo "Switching to django user for application startup..."
    exec gosu django "$@"
else
    # Execute the command passed to the script
    exec "$@"
fi