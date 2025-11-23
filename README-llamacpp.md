# 🚗 OpenLPR with LlamaCpp - Local Qwen3-VL-4B Inference

This guide provides comprehensive instructions for deploying OpenLPR with a local LlamaCpp inference server running Qwen3-VL-4B model for license plate recognition.

## 🏗️ Architecture Overview

The solution consists of three main components:

1. **LlamaCpp Service** - CPU-based inference server running Qwen3-VL-4B
2. **OpenLPR Service** - Django web application for license plate recognition
3. **Nginx Proxy** - Reverse proxy for production deployment (optional)

```mermaid
graph TB
    subgraph "Docker Network: openlpr-network"
        LC[LlamaCpp Container<br/>Port 8001]
        OL[OpenLPR Container<br/>Port 8000]
        NG[Nginx Container<br/>Port 80/443]
        
        LC --> |OpenAI API| OL
        NG --> |HTTP/HTTPS| OL
        NG --> |Internal API| LC
    end
    
    subgraph "Storage"
        MF[Model Files<br/>./models/]
        MC[Model Cache<br/>./model-cache/]
        DB[(Database<br/>./container-data/)]
        MD[Media Files<br/>./container-media/]
    end
    
    LC --> MF
    LC --> MC
    OL --> DB
    OL --> MD
```

## 📋 Prerequisites

### System Requirements

- **CPU**: 4+ cores recommended for optimal performance
- **RAM**: 8GB+ minimum, 16GB+ recommended
- **Storage**: 10GB+ free space for model and cache
- **Docker**: 20.10+ and Docker Compose 2.0+
- **HuggingFace Token**: For accessing gated models (if required)

### Software Dependencies

- Docker Engine 20.10+
- Docker Compose 2.0+
- Git (for cloning the repository)

## 🚀 Quick Start

### 1. Clone and Configure

```bash
# Clone the repository
git clone https://github.com/faisalthaheem/open-lpr.git
cd open-lpr

# Copy environment configuration
cp .env.llamacpp .env

# Edit the configuration
nano .env
```

### 2. Configure HuggingFace Token

Edit `.env.llamacpp` and set your HuggingFace token:

```env
HF_TOKEN=hf_your_huggingface_token_here
```

Get your token from: https://huggingface.co/settings/tokens

### 3. Start Services

```bash
# Start all services
docker compose -f docker-compose-llamacpp-cpu.yml up -d

# View logs
docker compose -f docker-compose-llamacpp-cpu.yml logs -f

# Check service status
docker compose -f docker-compose-llamacpp-cpu.yml ps
```

### 4. Access the Application

- **Web Interface**: http://localhost:8000
- **API Documentation**: http://localhost:8000/api/v1/
- **LlamaCpp API**: http://localhost:8001/v1/
- **Health Check**: http://localhost:8000/health/

## 📁 Project Structure

```
open-lpr/
├── docker-compose-llamacpp-cpu.yml    # Main compose file
├── .env.llamacpp                      # Environment configuration
├── scripts/
│   └── download-model.sh               # Model download script
├── nginx/
│   └── nginx.conf                     # Nginx configuration
├── models/                           # Model files (created by Docker)
├── model-cache/                       # HuggingFace cache (created by Docker)
├── container-data/                    # Database storage
├── container-media/                    # Media files
└── staticfiles/                       # Static files
```

## ⚙️ Configuration

### Environment Variables

Key configuration options in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `HF_TOKEN` | - | HuggingFace access token |
| `MODEL_REPO` | `unsloth/Qwen3-VL-4B-Instruct-GGUF` | Model repository |
| `MODEL_FILE` | `qwen3-vl-4b-instruct-q4_k_m.gguf` | Model filename |
| `N_CTX` | `4096` | Context size |
| `N_THREADS` | `4` | CPU threads for inference |
| `SECRET_KEY` | - | Django secret key |
| `DEBUG` | `False` | Django debug mode |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1,0.0.0.0` | Allowed hosts |

### Model Configuration

The default configuration uses:
- **Model**: Qwen3-VL-4B-Instruct (4-bit quantized)
- **Size**: ~2.7 GB
- **Format**: GGUF (compatible with LlamaCpp)
- **Quantization**: Q4_K_M (balanced quality/size)
- **Repository**: unsloth/Qwen3-VL-4B-Instruct-GGUF

## 🔧 Advanced Configuration

### Custom Model

To use a different model:

1. Update `.env.llamacpp`:
   ```env
   MODEL_REPO=your-repo/your-model
   MODEL_FILE=your-model-file.gguf
   ```

2. Restart services:
   ```bash
   docker compose -f docker-compose-llamacpp-cpu.yml down
   docker compose -f docker-compose-llamacpp-cpu.yml up -d
   ```

### Performance Tuning

Adjust CPU allocation in `.env`:

```env
# Increase for better performance (more CPU usage)
N_THREADS=8

# Increase for longer context (more RAM usage)
N_CTX=8192

# Adjust batch size
N_BATCH=1024
```

### Production Deployment

For production deployment with Nginx:

```bash
# Start with Nginx proxy
docker compose -f docker-compose-llamacpp-cpu.yml --profile production up -d

# Configure SSL certificates
mkdir -p nginx/ssl
# Copy your SSL certificates to nginx/ssl/
```

Update `nginx/nginx.conf` for your domain and SSL configuration.

## 📊 Monitoring and Health Checks

### Service Health

```bash
# Check all services
docker-compose -f docker-compose-llamacpp-cpu.yml ps

# Check OpenLPR health
curl http://localhost:8000/health/

# Check LlamaCpp health
curl http://localhost:8001/health

# View logs
docker-compose -f docker-compose-llamacpp-cpu.yml logs -f llamacpp
docker-compose -f docker-compose-llamacpp-cpu.yml logs -f lpr-app
```

### Performance Monitoring

Monitor resource usage:

```bash
# Resource usage
docker stats

# Disk usage
df -h
du -sh models/ model-cache/

# Memory usage
free -h
```

## 🐛 Troubleshooting

### Common Issues

#### 1. Model Download Fails

**Problem**: Model download fails or times out

**Solution**:
```bash
# Check HuggingFace token
echo $HF_TOKEN

# Manual download test
docker-compose -f docker-compose-llamacpp-cpu.yml exec llamacpp /scripts/download-model.sh

# Check available space
df -h
```

#### 2. Service Won't Start

**Problem**: Container fails to start

**Solution**:
```bash
# Check logs
docker-compose -f docker-compose-llamacpp-cpu.yml logs llamacpp

# Check configuration
docker-compose -f docker-compose-llamacpp-cpu.yml config

# Verify permissions
ls -la scripts/
chmod +x scripts/download-model.sh
```

#### 3. API Connection Errors

**Problem**: OpenLPR can't connect to LlamaCpp

**Solution**:
```bash
# Check network
docker network ls
docker network inspect openlpr_openlpr-network

# Test connectivity
docker-compose -f docker-compose-llamacpp-cpu.yml exec lpr-app curl http://llamacpp:8000/health

# Check ports
netstat -tlnp | grep :8000
netstat -tlnp | grep :8001
```

#### 4. Memory Issues

**Problem**: Out of memory errors

**Solution**:
```bash
# Reduce context size
N_CTX=2048

# Reduce threads
N_THREADS=2

# Check memory usage
docker stats llamacpp
```

### Debug Mode

Enable debug logging:

```bash
# Set debug mode
echo "DEBUG=True" >> .env.llamacpp

# Restart with verbose logs
docker-compose -f docker-compose-llamacpp-cpu.yml down
docker-compose -f docker-compose-llamacpp-cpu.yml up --build
```

## 🔄 Maintenance

### Updates

```bash
# Pull latest images
docker-compose -f docker-compose-llamacpp-cpu.yml pull

# Restart with updates
docker-compose -f docker-compose-llamacpp-cpu.yml up -d --force-recreate
```

### Backup

```bash
# Backup database
docker-compose -f docker-compose-llamacpp-cpu.yml exec lpr-app cp /app/data/db.sqlite3 /app/data/db.sqlite3.backup

# Backup media files
tar -czf container-media-backup-$(date +%Y%m%d).tar.gz container-media/

# Backup model cache
tar -czf model-cache-backup-$(date +%Y%m%d).tar.gz model-cache/
```

### Cleanup

```bash
# Remove unused images
docker image prune -f

# Remove unused volumes
docker volume prune -f

# Clean model cache (redownload required)
rm -rf model-cache/*
```

## 📚 API Usage

### OpenLPR API

The OpenLPR API remains unchanged. See `API_DOCUMENTATION.md` for details.

### LlamaCpp API

Direct access to LlamaCpp API:

```bash
# List models
curl http://localhost:8001/v1/models

# Chat completion
curl -X POST http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4-vision-preview",
    "messages": [
      {
        "role": "user",
        "content": "Hello, how are you?"
      }
    ]
  }'
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- [Qwen3-VL](https://huggingface.co/unsloth/Qwen3-VL-4B-Instruct-GGUF) for the vision-language model
- [LlamaCpp](https://github.com/ggerganov/llama.cpp) for the inference engine
- [OpenLPR](https://github.com/faisalthaheem/open-lpr) for the license plate recognition system
- [HuggingFace](https://huggingface.co/) for model hosting

---

## 📞 Support

For issues and support:

1. Check this documentation
2. Search existing GitHub issues
3. Create a new issue with:
   - System information
   - Error logs
   - Configuration details
   - Steps to reproduce

**Note**: This setup provides local inference, eliminating dependency on external API services and ensuring data privacy.