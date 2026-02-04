#!/bin/bash
# Build script for custom monitoring images (Prometheus, Grafana, Blackbox Exporter)
# These images have configurations baked in for Coolify compatibility

set -e

# Configuration
REGISTRY="ghcr.io/faisalthaheem"
VERSION=${1:-latest}
PUSH=${2:-false}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "Building OpenLPR Custom Monitoring Images"
echo "=========================================="
echo "Registry: $REGISTRY"
echo "Version: $VERSION"
echo "Push to registry: $PUSH"
echo ""

# Function to build and optionally push an image
build_image() {
    local name=$1
    local dockerfile=$2
    local image_name="${REGISTRY}/open-lpr-${name}:${VERSION}"
    local latest_name="${REGISTRY}/open-lpr-${name}:latest"
    
    echo -e "${YELLOW}Building ${name}...${NC}"
    
    # Build the image
    docker build -f "$dockerfile" -t "$image_name" -t "$latest_name" .
    
    echo -e "${GREEN}✓ ${name} built successfully${NC}"
    
    # Push if requested
    if [ "$PUSH" = "true" ]; then
        echo -e "${YELLOW}Pushing ${name} to registry...${NC}"
        docker push "$image_name"
        docker push "$latest_name"
        echo -e "${GREEN}✓ ${name} pushed successfully${NC}"
    fi
    
    echo ""
}

# Check if docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running. Please start Docker and try again.${NC}"
    exit 1
fi

# Build Prometheus
build_image "prometheus" "Dockerfile.prometheus"

# Build Grafana
build_image "grafana" "Dockerfile.grafana"

# Build Blackbox Exporter
build_image "blackbox" "Dockerfile.blackbox"

echo "=========================================="
echo -e "${GREEN}All monitoring images built successfully!${NC}"
echo "=========================================="
echo ""
echo "Images built:"
echo "  - ${REGISTRY}/open-lpr-prometheus:${VERSION}"
echo "  - ${REGISTRY}/open-lpr-grafana:${VERSION}"
echo "  - ${REGISTRY}/open-lpr-blackbox:${VERSION}"
echo ""

if [ "$PUSH" = "true" ]; then
    echo "All images have been pushed to the registry."
    echo "You can now deploy to Coolify using these images."
else
    echo "To push images to the registry, run:"
    echo "  ./build-monitoring-images.sh ${VERSION} true"
    echo ""
    echo "To test locally:"
    echo "  docker-compose up -d"
fi