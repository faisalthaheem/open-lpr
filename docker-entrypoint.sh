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

# Check if the metrics directory exists
if [ ! -d "/app/metrics" ]; then
    echo "Creating metrics directory for persistent metrics storage..."
    mkdir -p /app/metrics
fi

# Ensure proper permissions for metrics directory
# Run as root to set permissions, then switch back
if [ "$(id -u)" = "0" ]; then
    chown -R django:django /app/metrics
    chmod -R 755 /app/metrics
else
    echo "Warning: Running as non-root, may not be able to set metrics permissions"
fi

# Check if the static root exists (collectstatic target)
if [ ! -d "/app/staticfiles" ]; then
    echo "Creating staticfiles directory for collected static assets..."
    mkdir -p /app/staticfiles
fi

if [ "$(id -u)" = "0" ]; then
    chown -R django:django /app/staticfiles
    chmod -R 755 /app/staticfiles
fi

# Change to app directory
cd /app

# Create a simple log file to ensure it exists and has right permissions
touch /app/data/django.log 2>/dev/null || true
if [ "$(id -u)" = "0" ]; then
    chown django:django /app/data/django.log
    chmod 644 /app/data/django.log
fi

# Create metrics state file to ensure it exists and has right permissions
touch /app/metrics/metrics_state.json 2>/dev/null || true
if [ "$(id -u)" = "0" ]; then
    chown django:django /app/metrics/metrics_state.json
    chmod 644 /app/metrics/metrics_state.json
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

# Verify the local pipeline's model artifacts before serving traffic.
#
# PIPELINE_BACKEND defaults to local, so a deployment whose artifacts are missing
# would start fine and then fail every upload. Failing at startup makes the cause
# visible in the logs before requests arrive, rather than as 500s afterwards.
if [ "$PIPELINE_BACKEND" = "local" ]; then
    MODEL_DIR="${PIPELINE_MODEL_DIR:-/app/model/plate}"
    MISSING=""
    for REQUIRED in \
        "${PIPELINE_DETECTOR_MODEL:-plate_yolox_tiny_640.onnx}" \
        "${PIPELINE_OCR_MODEL:-plate_ocr_ppocrv5_mobile.onnx}" \
        "${PIPELINE_OCR_DICT:-plate_ocr_dict.json}"
    do
        if [ ! -f "$MODEL_DIR/$REQUIRED" ]; then
            MISSING="$MISSING
  $MODEL_DIR/$REQUIRED"
        fi
    done
    if [ -n "$MISSING" ]; then
        echo "ERROR: PIPELINE_BACKEND=local but these model artifacts are missing:$MISSING" >&2
        echo "Mount or download them into PIPELINE_MODEL_DIR, or set PIPELINE_BACKEND=llm to use the external API." >&2
        exit 1
    fi
    echo "Local pipeline artifacts verified in $MODEL_DIR"
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