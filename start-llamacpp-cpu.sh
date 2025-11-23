#!/bin/bash

# Quick Start Script for OpenLPR + LlamaCpp
# This script sets up and starts the complete stack

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Script configuration
COMPOSE_FILE="docker-compose-llamacpp-cpu.yml"
ENV_FILE=".env.llamacpp"
ENV_TEMPLATE=".env.llamacpp"

# Check dependencies
check_dependencies() {
    log_info "Checking dependencies..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! docker compose version &> /dev/null; then
        log_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    log_success "Dependencies check passed"
}

# Setup environment
setup_environment() {
    log_info "Setting up environment..."
    
    if [[ ! -f "$ENV_FILE" ]]; then
        log_info "Creating environment file from template..."
        cp "$ENV_TEMPLATE" "$ENV_FILE"
        log_warning "Please edit $ENV_FILE and set your HF_TOKEN"
        log_info "Get your token from: https://huggingface.co/settings/tokens"
        
        # Ask if user wants to edit now
        read -p "Do you want to edit the environment file now? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            ${EDITOR:-nano} "$ENV_FILE"
        fi
    else
        log_info "Environment file already exists"
    fi
    
    # Check if HF_TOKEN is set
    if grep -q "HF_TOKEN=your_huggingface_token_here" "$ENV_FILE"; then
        log_warning "HF_TOKEN is not set in $ENV_FILE"
        log_info "Please edit the file and set your HuggingFace token"
        return 1
    fi
    
    log_success "Environment setup complete"
    return 0
}

# Create necessary directories
create_directories() {
    log_info "Creating necessary directories..."
    
    mkdir -p container-data
    mkdir -p container-media
    mkdir -p staticfiles
    mkdir -p model_files
    mkdir -p model_files_cache
    mkdir -p nginx/ssl
    
    log_success "Directories created"
}

# Pull Docker images
pull_images() {
    log_info "Pulling Docker images..."
    
    docker compose -f "$COMPOSE_FILE" pull
    
    log_success "Docker images pulled"
}

# Start services
start_services() {
    log_info "Starting services..."
    
    # Start with detached mode
    docker compose -f "$COMPOSE_FILE" up -d
    
    log_success "Services started"
}

# Wait for services to be healthy
wait_for_services() {
    log_info "Waiting for services to be healthy..."
    
    local max_attempts=30
    local attempt=1
    
    while [[ $attempt -le $max_attempts ]]; do
        log_info "Health check attempt $attempt of $max_attempts..."
        
        # Check LlamaCpp
        if curl -f http://localhost:8001/health &>/dev/null; then
            log_success "LlamaCpp service is healthy"
        else
            log_warning "LlamaCpp service not ready yet"
        fi
        
        # Check OpenLPR
        if curl -f http://localhost:8000/health/ &>/dev/null; then
            log_success "OpenLPR service is healthy"
        else
            log_warning "OpenLPR service not ready yet"
        fi
        
        # Check if both are healthy
        if curl -f http://localhost:8001/health &>/dev/null && curl -f http://localhost:8000/health/ &>/dev/null; then
            log_success "All services are healthy!"
            return 0
        fi
        
        sleep 10
        ((attempt++))
    done
    
    log_error "Services did not become healthy within expected time"
    return 1
}

# Show status
show_status() {
    log_info "Service status:"
    docker compose -f "$COMPOSE_FILE" ps
    
    echo
    log_info "Access URLs:"
    echo "  🌐 OpenLPR Web Interface: http://localhost:8000"
    echo "  📚 OpenLPR API: http://localhost:8000/api/v1/"
    echo "  🤖 LlamaCpp API: http://localhost:8001/v1/"
    echo "  ❤️  Health Check: http://localhost:8000/health/"
    echo
    log_info "Useful commands:"
    echo "  📋 View logs: docker compose -f $COMPOSE_FILE logs -f"
    echo "  🛑 Stop services: docker compose -f $COMPOSE_FILE down"
    echo "  🧪 Test integration: ./test-llamacpp-integration.py"
}

# Main execution
main() {
    echo "🚗 OpenLPR + LlamaCpp Quick Start"
    echo "=================================="
    echo
    
    check_dependencies
    
    if ! setup_environment; then
        log_error "Please set up your environment first"
        exit 1
    fi
    
    create_directories
    pull_images
    start_services
    
    if wait_for_services; then
        show_status
        
        log_success "🎉 Setup complete! Your OpenLPR + LlamaCpp stack is running."
        log_info "Run './test-llamacpp-integration.py' to verify everything is working."
    else
        log_error "❌ Setup failed. Check the logs with 'docker compose -f $COMPOSE_FILE logs'"
        exit 1
    fi
}

# Handle script interruption
trap 'log_warning "Setup interrupted by user"; exit 130' INT

# Run main function
main "$@"