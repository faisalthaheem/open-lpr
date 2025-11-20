# Multi-stage Dockerfile for Open LPR Application
# Stage 1: Base stage with Python dependencies
FROM python:3.11-slim AS base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# Create and activate virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip
RUN pip install --upgrade pip

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Verify gunicorn is installed
RUN which gunicorn || (echo "Gunicorn not found in PATH" && exit 1)

# Stage 2: Build stage for application code
FROM base AS builder

# Set work directory
WORKDIR /app

# Copy application code
COPY . .

# Create directories for volumes
RUN mkdir -p /app/data /app/media /app/staticfiles

# Collect static files
RUN python manage.py collectstatic --noinput

# Stage 3: Production stage
FROM base AS production

# Create non-root user
RUN groupadd -r django && useradd -r -g django django

# Set work directory
WORKDIR /app

# Create directories with proper permissions
RUN mkdir -p /app/data /app/media /app/staticfiles && \
    chown -R django:django /app && \
    chmod -R 755 /app/data /app/media /app/staticfiles

# Copy application from builder stage
COPY --from=builder --chown=django:django /app /app

# Ensure PATH is set correctly for the virtual environment
ENV PATH="/opt/venv/bin:$PATH"

# Switch to non-root user
USER django

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD python manage.py check || exit 1

# Default command
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120", "lpr_project.wsgi:application"]