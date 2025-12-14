#!/bin/bash

# Open LPR Docker Image Build Script
# This script builds the latest Docker image for the Open LPR application
# Based on the GitHub workflow at .github/workflows/docker-publish.yml

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
IMAGE_NAME="open-lpr"
REGISTRY="ghcr.io"
REPOSITORY_OWNER="faisalthaheem"
TAG="latest"
PLATFORMS="linux/amd64,linux/arm64"
PUSH=false
BUILD_CACHE=true
NO_CACHE=false
SBOM=false
HELP=false
VERBOSE=false

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show help
show_help() {
    cat << EOF
Open LPR Docker Image Build Script

USAGE:
    $0 [OPTIONS]

OPTIONS:
    -t, --tag TAG           Docker image tag (default: latest)
    -n, --name NAME         Image name (default: open-lpr)
    -r, --registry REGISTRY Container registry (default: ghcr.io)
    -o, --owner OWNER       Repository owner (default: faisalthaheem)
    -p, --push              Push image to registry after build
    -c, --no-cache          Disable build cache
    --platforms PLATFORMS   Target platforms (default: linux/amd64,linux/arm64)
    --sbom                  Generate SBOM after build
    --build-cache           Use build cache (default: true)
    -v, --verbose           Verbose output
    -h, --help              Show this help message

EXAMPLES:
    # Build local image with latest tag
    $0

    # Build and push with custom tag
    $0 --tag v1.2.3 --push

    # Build for specific platform only
    $0 --platforms linux/amd64

    # Build without cache
    $0 --no-cache

    # Generate SBOM after build
    $0 --sbom

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -t|--tag)
            TAG="$2"
            shift 2
            ;;
        -n|--name)
            IMAGE_NAME="$2"
            shift 2
            ;;
        -r|--registry)
            REGISTRY="$2"
            shift 2
            ;;
        -o|--owner)
            REPOSITORY_OWNER="$2"
            shift 2
            ;;
        -p|--push)
            PUSH=true
            shift
            ;;
        -c|--no-cache)
            NO_CACHE=true
            BUILD_CACHE=false
            shift
            ;;
        --platforms)
            PLATFORMS="$2"
            shift 2
            ;;
        --sbom)
            SBOM=true
            shift
            ;;
        --build-cache)
            BUILD_CACHE=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -h|--help)
            HELP=true
            shift
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Show help if requested
if [ "$HELP" = true ]; then
    show_help
    exit 0
fi

# Construct full image name
FULL_IMAGE_NAME="${REGISTRY}/${REPOSITORY_OWNER}/${IMAGE_NAME}:${TAG}"

# Validate Docker installation
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed or not in PATH"
    exit 1
fi

# Check if Docker Buildx is available
if ! docker buildx version &> /dev/null; then
    print_error "Docker Buildx is not available. Please install Docker Buildx."
    exit 1
fi

# Check if we're logged in to registry (if pushing)
if [ "$PUSH" = true ]; then
    if ! docker info | grep -q "Username"; then
        print_warning "Not logged in to Docker registry. Please run 'docker login' first."
    fi
fi

# Main build function
build_image() {
    print_status "Starting Docker image build for Open LPR application..."
    print_status "Image: ${FULL_IMAGE_NAME}"
    print_status "Platforms: ${PLATFORMS}"
    
    # Create buildx builder if it doesn't exist
    BUILDER_NAME="openlpr-builder"
    if ! docker buildx ls | grep -q "$BUILDER_NAME"; then
        print_status "Creating Docker Buildx builder: $BUILDER_NAME"
        docker buildx create --name "$BUILDER_NAME" --driver docker-container --use --bootstrap
    else
        docker buildx use "$BUILDER_NAME"
    fi

    # Check if building for multiple platforms locally and handle accordingly
    if [ "$PUSH" = false ] && [[ "$PLATFORMS" == *","* ]]; then
        print_warning "Cannot load multiple platforms locally. Building for first platform only or use --push to push to registry."
        # Extract first platform for local build
        FIRST_PLATFORM=$(echo "$PLATFORMS" | cut -d',' -f1)
        BUILD_ARGS=(
            "--platform" "$FIRST_PLATFORM"
            "--tag" "$FULL_IMAGE_NAME"
            "--file" "./Dockerfile"
            "."
        )
        print_status "Building for platform: $FIRST_PLATFORM"
    else
        # Prepare build arguments for single platform or push
        BUILD_ARGS=(
            "--platform" "$PLATFORMS"
            "--tag" "$FULL_IMAGE_NAME"
            "--file" "./Dockerfile"
            "."
        )
    fi

    # Add cache configuration
    if [ "$BUILD_CACHE" = true ]; then
        BUILD_ARGS+=("--cache-from" "type=gha")
        BUILD_ARGS+=("--cache-to" "type=gha,mode=max")
        print_status "Using GitHub Actions cache"
    fi

    if [ "$NO_CACHE" = true ]; then
        BUILD_ARGS+=("--no-cache")
        print_status "Build cache disabled"
    fi

    # Add verbose output if requested
    if [ "$VERBOSE" = true ]; then
        BUILD_ARGS+=("--progress" "plain")
    fi

    # Add push flag if requested
    if [ "$PUSH" = true ]; then
        BUILD_ARGS+=("--push")
        print_status "Will push image to registry after build"
    else
        # Only add --load for single platform builds
        if [[ "$PLATFORMS" != *","* ]]; then
            BUILD_ARGS+=("--load")
            print_status "Will load image locally"
        fi
    fi

    # Extract metadata (similar to GitHub workflow)
    print_status "Extracting build metadata..."
    
    # Get git commit info
    GIT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
    GIT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
    BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    
    print_status "Git commit: ${GIT_COMMIT}"
    print_status "Git branch: ${GIT_BRANCH}"
    print_status "Build date: ${BUILD_DATE}"

    # Add labels
    BUILD_ARGS+=(
        "--label" "org.opencontainers.image.title=${IMAGE_NAME}"
        "--label" "org.opencontainers.image.description=Open LPR - License Plate Recognition Application"
        "--label" "org.opencontainers.image.url=https://github.com/${REPOSITORY_OWNER}/${IMAGE_NAME}"
        "--label" "org.opencontainers.image.source=https://github.com/${REPOSITORY_OWNER}/${IMAGE_NAME}"
        "--label" "org.opencontainers.image.version=${TAG}"
        "--label" "org.opencontainers.image.created=${BUILD_DATE}"
        "--label" "org.opencontainers.image.revision=${GIT_COMMIT}"
        "--label" "org.opencontainers.image.branch=${GIT_BRANCH}"
        "--label" "org.opencontainers.image.licenses=MIT"
    )

    # Build the image
    print_status "Building Docker image..."
    if [ "$VERBOSE" = true ]; then
        print_status "Build command: docker buildx build ${BUILD_ARGS[*]}"
    fi

    if docker buildx build "${BUILD_ARGS[@]}"; then
        print_success "Docker image built successfully: ${FULL_IMAGE_NAME}"
    else
        print_error "Docker build failed"
        exit 1
    fi
}

# Function to generate SBOM
generate_sbom() {
    if [ "$SBOM" = true ]; then
        print_status "Generating SBOM..."
        
        # Check if syft is available
        if command -v syft &> /dev/null; then
            syft "${FULL_IMAGE_NAME}" -o spdx-json -o "sbom-${TAG}.spdx.json"
            print_success "SBOM generated: sbom-${TAG}.spdx.json"
        else
            print_warning "syft is not installed. Skipping SBOM generation."
            print_warning "Install syft with: curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh | sh -s -- -b /usr/local/bin"
        fi
    fi
}

# Function to show image information
show_image_info() {
    print_status "Image information:"
    
    # Show image size
    if docker images --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}" | grep -E "${IMAGE_NAME}:${TAG}"; then
        :
    else
        print_warning "Image size information not available (might be a remote image)"
    fi
    
    # Show image digest if available
    if docker manifest inspect "${FULL_IMAGE_NAME}" &> /dev/null; then
        DIGEST=$(docker manifest inspect "${FULL_IMAGE_NAME}" | jq -r '.manifests[0].digest' 2>/dev/null || echo "N/A")
        print_status "Image digest: ${DIGEST}"
    fi
}

# Function to run basic tests
run_tests() {
    print_status "Running basic container tests..."
    
    # Test if image exists locally
    if docker images --format "{{.Repository}}:{{.Tag}}" | grep -q "${FULL_IMAGE_NAME}"; then
        print_status "Testing container startup..."
        
        # Create a temporary container to test
        CONTAINER_NAME="test-$(date +%s)"
        
        if docker run --name "$CONTAINER_NAME" --rm -d \
            -e DEBUG=False \
            -e SECRET_KEY=test-key-for-build-validation \
            "${FULL_IMAGE_NAME}" sleep 10 &> /dev/null; then
            
            # Check if container is running
            if docker ps --format "{{.Names}}" | grep -q "$CONTAINER_NAME"; then
                print_success "Container startup test passed"
                docker stop "$CONTAINER_NAME" &> /dev/null
            else
                print_error "Container startup test failed"
                docker logs "$CONTAINER_NAME" 2>&1 | tail -10
                exit 1
            fi
        else
            print_warning "Container startup test could not be performed"
        fi
    else
        print_warning "Image not available locally for testing (remote build)"
    fi
}

# Main execution
main() {
    print_status "Open LPR Docker Build Script"
    print_status "============================"
    
    # Show configuration
    print_status "Configuration:"
    print_status "  Image Name: ${IMAGE_NAME}"
    print_status "  Tag: ${TAG}"
    print_status "  Full Name: ${FULL_IMAGE_NAME}"
    print_status "  Registry: ${REGISTRY}"
    print_status "  Owner: ${REPOSITORY_OWNER}"
    print_status "  Platforms: ${PLATFORMS}"
    print_status "  Push: ${PUSH}"
    print_status "  Build Cache: ${BUILD_CACHE}"
    print_status "  Generate SBOM: ${SBOM}"
    echo ""
    
    # Build the image
    build_image
    
    # Generate SBOM if requested
    generate_sbom
    
    # Show image information
    show_image_info
    
    # Run basic tests
    run_tests
    
    print_success "Build process completed successfully!"
    
    if [ "$PUSH" = false ]; then
        print_status "To push the image later, run:"
        print_status "  docker push ${FULL_IMAGE_NAME}"
    fi
    
    if [ "$PUSH" = true ]; then
        print_status "Image pushed to registry: ${FULL_IMAGE_NAME}"
    fi
}

# Check if we're in the right directory
if [ ! -f "Dockerfile" ]; then
    print_error "Dockerfile not found in current directory"
    print_error "Please run this script from the Open LPR project root"
    exit 1
fi

# Run main function
main "$@"
