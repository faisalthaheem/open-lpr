# Open LPR Docker Build Script

This document provides instructions for using the `build-docker-image.sh` utility script to build Docker images for the Open LPR application.

## Overview

The `build-docker-image.sh` script is a comprehensive utility that automates the Docker image build process for the Open LPR (License Plate Recognition) application. It's based on the GitHub Actions workflow at `.github/workflows/docker-publish.yml` and provides similar functionality for local development and CI/CD pipelines.

## Features

- **Multi-platform builds**: Supports `linux/amd64` and `linux/arm64` by default
- **Flexible tagging**: Custom image tags and registry configuration
- **Build caching**: Optional GitHub Actions cache integration
- **SBOM generation**: Optional Software Bill of Materials generation
- **Container testing**: Basic container startup validation
- **Metadata labeling**: Automatic OpenContainers metadata injection
- **Verbose output**: Detailed build logging option

## Prerequisites

- Docker Engine with Buildx support
- Bash shell
- Git (for metadata extraction)

### Optional Dependencies

- `syft` - for SBOM generation (install with: `curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh | sh -s -- -b /usr/local/bin`)
- `jq` - for manifest inspection

## Usage

### Basic Usage

```bash
# Build local image with latest tag
./build-docker-image.sh

# Show help
./build-docker-image.sh --help
```

### Advanced Usage

```bash
# Build with custom tag
./build-docker-image.sh --tag v1.2.3

# Build and push to registry
./build-docker-image.sh --tag v1.2.3 --push

# Build for specific platform only
./build-docker-image.sh --platforms linux/amd64

# Build without cache
./build-docker-image.sh --no-cache

# Generate SBOM
./build-docker-image.sh --sbom

# Verbose output
./build-docker-image.sh --verbose

# Custom registry and owner
./build-docker-image.sh --registry docker.io --owner myusername --tag myapp
```

## Command Line Options

| Option | Short | Description | Default |
|--------|--------|-------------|-----------|
| `--tag` | `-t` | Docker image tag | `latest` |
| `--name` | `-n` | Image name | `open-lpr` |
| `--registry` | `-r` | Container registry | `ghcr.io` |
| `--owner` | `-o` | Repository owner | `faisalthaheem` |
| `--push` | `-p` | Push image to registry after build | `false` |
| `--no-cache` | `-c` | Disable build cache | `false` |
| `--platforms` | | Target platforms | `linux/amd64,linux/arm64` |
| `--sbom` | | Generate SBOM after build | `false` |
| `--build-cache` | | Use build cache | `true` |
| `--verbose` | `-v` | Verbose output | `false` |
| `--help` | `-h` | Show help message | - |

## Default Configuration

The script uses the following default values:

- **Image Name**: `open-lpr`
- **Registry**: `ghcr.io`
- **Owner**: `faisalthaheem`
- **Tag**: `latest`
- **Platforms**: `linux/amd64,linux/arm64`
- **Full Image Name**: `ghcr.io/faisalthaheem/open-lpr:latest`

## Build Process

The script performs the following steps:

1. **Validation**: Checks Docker and Buildx installation
2. **Builder Setup**: Creates/uses a dedicated Buildx builder
3. **Metadata Extraction**: Extracts Git commit, branch, and build date
4. **Image Build**: Builds the Docker image with proper labels and cache
5. **SBOM Generation** (optional): Creates Software Bill of Materials
6. **Image Information**: Displays size and digest information
7. **Container Testing**: Validates container startup
8. **Push** (optional): Pushes to registry if requested

## Generated Labels

The script automatically adds OpenContainers labels to the image:

- `org.opencontainers.image.title` - Image title
- `org.opencontainers.image.description` - Image description
- `org.opencontainers.image.url` - Repository URL
- `org.opencontainers.image.source` - Source code URL
- `org.opencontainers.image.version` - Image version/tag
- `org.opencontainers.image.created` - Build timestamp
- `org.opencontainers.image.revision` - Git commit hash
- `org.opencontainers.image.branch` - Git branch
- `org.opencontainers.image.licenses` - License information

## Output Examples

### Successful Build

```bash
[INFO] Open LPR Docker Build Script
[INFO] ============================
[INFO] Configuration:
[INFO]   Image Name: open-lpr
[INFO]   Tag: latest
[INFO]   Full Name: ghcr.io/faisalthaheem/open-lpr:latest
[INFO]   Registry: ghcr.io
[INFO]   Owner: faisalthaheem
[INFO]   Platforms: linux/amd64
[INFO]   Push: false
[INFO]   Build Cache: true
[INFO]   Generate SBOM: false

[INFO] Starting Docker image build for Open LPR application...
...
[SUCCESS] Docker image built successfully: ghcr.io/faisalthaheem/open-lpr:latest
[INFO] Image information:
ghcr.io/faisalthaheem/open-lpr:latest                                                                   652MB     2025-12-13 20:52:53 -0800 PST
[INFO] Image digest: sha256:ecbed71813767d3ada5bc2b0e2749a87631d9e137551d65faa4bc213f9ae89d4
[INFO] Running basic container tests...
[SUCCESS] Container startup test passed
[SUCCESS] Build process completed successfully!
```

## Integration with CI/CD

The script is designed to work seamlessly in CI/CD environments:

### GitHub Actions

```yaml
- name: Build Docker image
  run: |
    chmod +x build-docker-image.sh
    ./build-docker-image.sh --tag ${{ github.sha }} --push
```

### GitLab CI

```yaml
build_image:
  script:
    - chmod +x build-docker-image.sh
    - ./build-docker-image.sh --tag $CI_COMMIT_SHA --push
```

## Troubleshooting

### Common Issues

1. **Docker Buildx not available**
   ```bash
   # Install Buildx
   docker buildx install
   ```

2. **Permission denied**
   ```bash
   # Make script executable
   chmod +x build-docker-image.sh
   ```

3. **Registry login required**
   ```bash
   # Login to registry
   docker login ghcr.io
   ```

4. **Build context too large**
   - Check `.dockerignore` file
   - Exclude unnecessary files and directories

### Debug Mode

Enable verbose output for detailed debugging:

```bash
./build-docker-image.sh --verbose
```

## Comparison with GitHub Actions

This script replicates the functionality of `.github/workflows/docker-publish.yml`:

| GitHub Actions | Script Equivalent |
|---------------|-------------------|
| `docker/setup-buildx-action@v3` | Built-in Buildx setup |
| `docker/login-action@v3` | `docker login` |
| `docker/metadata-action@v5` | Built-in metadata extraction |
| `docker/build-push-action@v5` | `docker buildx build` |
| `anchore/sbom-action@v0.17.2` | Optional `syft` integration |

## Contributing

When modifying the script:

1. Maintain compatibility with existing options
2. Update help text for new features
3. Test with multiple platforms
4. Validate container startup functionality
5. Update this documentation

## License

This script follows the same license as the Open LPR project (MIT).
