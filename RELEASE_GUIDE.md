# Release Guide for Open LPR

This document explains the release process and the release notes files.

## Files Created for v1.1.0

1. [`RELEASE_NOTES_v1.1.0.md`](docs/RELEASE_NOTES_v1.1.0.md) — Comprehensive release notes
2. [`GITHUB_RELEASE_v1.1.0.md`](GITHUB_RELEASE_v1.1.0.md) — GitHub release page content
3. [`CHANGELOG.md`](CHANGELOG.md) — Project changelog (updated with v1.1.0 section)

## Release Process

### 1. Commit and Push Release Files

```bash
git add CHANGELOG.md docs/RELEASE_NOTES_v1.1.0.md GITHUB_RELEASE_v1.1.0.md RELEASE_GUIDE.md
git commit -m "docs: prepare v1.1.0 release notes"
git push origin main
```

### 2. Create and Push the Tag

```bash
git tag -a v1.1.0 -m "Release v1.1.0"
git push origin v1.1.0
```

### 3. Create the GitHub Release

1. Go to https://github.com/faisalthaheem/open-lpr/releases/new
2. Choose the `v1.1.0` tag
3. Set release title: `v1.1.0`
4. Copy the content from [`GITHUB_RELEASE_v1.1.0.md`](GITHUB_RELEASE_v1.1.0.md) into the description
5. Click "Publish release"

### 4. Automated CI/CD

The GitHub Actions workflow (`.github/workflows/docker-publish.yml`) will automatically:
- Build the Docker image for **linux/amd64** and **linux/arm64**
- Publish to GitHub Container Registry with tags:
  - `ghcr.io/faisalthaheem/open-lpr:latest`
  - `ghcr.io/faisalthaheem/open-lpr:v1.1.0`
  - `ghcr.io/faisalthaheem/open-lpr:v1.1`
  - `ghcr.io/faisalthaheem/open-lpr:v1`
- Generate SBOM for security scanning

## Previous Releases

### v1.0.0
- [`RELEASE_NOTES_v1.0.0.md`](RELEASE_NOTES_v1.0.0.md)
- [`GITHUB_RELEASE_v1.0.0.md`](GITHUB_RELEASE_v1.0.0.md)