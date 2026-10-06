# Open LPR v1.0.0 Release Notes

We're excited to announce the first major release of Open LPR - a powerful, open-source License Plate Recognition system powered by AI!

## 🎉 What is Open LPR?

Open LPR is a Django-based web application that uses the Qwen3-VL AI model to detect and recognize license plates in images with advanced OCR capabilities. The system provides both a user-friendly web interface and a comprehensive REST API for integration into other applications.

## ✨ Key Features

- 🤖 **AI-Powered Detection**: Uses qwen3-vl-4b-instruct vision-language model for accurate license plate recognition
- 🔍 **Advanced OCR Integration**: Extracts text from detected license plates with confidence scores
- 🎯 **Bounding Box Visualization**: Draws colored boxes around detected plates and OCR text
- 📤 **Drag & Drop Upload**: Modern, user-friendly file upload interface
- 💾 **Permanent Storage**: All uploaded and processed images are saved permanently
- 🔄 **Side-by-Side Comparison**: View original and processed images together
- 🔎 **Search & Filter**: Browse and search through processing history
- 📱 **Responsive Design**: Works on desktop, tablet, and mobile devices
- 🐳 **Docker Support**: Easy deployment with Docker and Docker Compose
- 🔌 **REST API**: Full API for programmatic access

## 🚀 Deployment Options

This release provides multiple deployment options:

1. **Standard Docker Deployment**: Traditional deployment with cloud-based AI services
2. **LlamaCpp CPU Deployment**: Local inference using CPU resources
3. **LlamaCpp GPU Deployment**: Local inference with AMD GPU acceleration using Vulkan

## 📦 What's New in v1.0.0

### Core Application
- Complete Django web application with license plate recognition capabilities
- RESTful API with comprehensive endpoints for image processing
- User-friendly web interface with drag-and-drop upload functionality
- Image processing pipeline with bounding box visualization
- Search and filter functionality for processed images
- Responsive design that works across all devices

### Docker Deployment
- Multi-stage optimized Dockerfile for production use
- Automated CI/CD pipeline with GitHub Actions
- Multi-architecture support (linux/amd64, linux/arm64)
- Automatic publishing to GitHub Container Registry
- Software Bill of Materials (SBOM) generation for security scanning

### LlamaCpp Integration
- Local inference support with LlamaCpp server
- CPU and GPU deployment options
- Comprehensive documentation for local deployment
- Environment configuration templates
- Model download automation

### Documentation
- Comprehensive README with visual showcase
- Detailed API documentation
- Docker deployment guide
- LlamaCpp and ROCm resources collection
- Troubleshooting guides and best practices

## 🔧 Technical Improvements

### Performance
- Optimized Docker image for production use
- Gunicorn WSGI server with 3 workers
- Efficient image processing pipeline
- Configurable batch processing

### Security
- Non-root Docker user for security
- Environment-based configuration
- Secure file upload handling
- Input validation and sanitization

### Developer Experience
- Well-structured codebase following Django best practices
- Comprehensive documentation
- Environment configuration templates
- Management commands for project setup

## 📋 API Endpoints

### Web Endpoints
- `GET /` - Home page with upload form
- `POST /upload/` - Upload and process image
- `GET /result/<int:image_id>/` - View processing results
- `GET /images/` - Browse image history with search and filtering
- `GET /image/<int:image_id>/` - View detailed image information
- `POST /progress/` - Check processing status (AJAX endpoint)
- `GET /download/<int:image_id>/<str:image_type>/` - Download images
- `GET /health/` - API health check endpoint

### REST API Endpoints
- `POST /api/v1/ocr/` - Upload an image and receive OCR results

## 🐳 Docker Images

The v1.0.0 release includes Docker images published to GitHub Container Registry:

- `ghcr.io/faisalthaheem/open-lpr:latest` - Latest stable version
- `ghcr.io/faisalthaheem/open-lpr:v1.0.0` - Version 1.0.0
- `ghcr.io/faisalthaheem/open-lpr:v1.0` - Version 1.0.x series
- `ghcr.io/faisalthaheem/open-lpr:v1` - Version 1.x series

Images are available for both linux/amd64 and linux/arm64 architectures.

## 📚 Documentation

- [Main README](../README.md) - Project overview and quick start guide
- [Docker Deployment Guide](../DOCKER_DEPLOYMENT.md) - Comprehensive Docker deployment instructions
- [LlamaCpp Deployment Guide](LLAMACPP.md) - Local inference with LlamaCpp server
- [API Documentation](../API_DOCUMENTATION.md) - Complete REST API reference
- [LlamaCpp Resources](LLAMACPP_RESOURCES.md) - Important URLs and documentation links

## 🔄 Migration Notes

This is the initial release, so there are no migration requirements. Future releases will include migration guides as needed.

## 🐛 Known Issues

- Large images (>10MB) may require increased memory allocation
- GPU acceleration is currently limited to AMD GPUs with Vulkan support
- Concurrent processing is limited by Django's development server (use Gunicorn in production)

## 🛣️ Roadmap

Future releases will include:

- Support for additional GPU types (NVIDIA CUDA)
- Batch processing capabilities
- Real-time video stream processing
- Additional language support for license plates
- Performance optimizations
- Mobile application

## 🤝 Contributing

We welcome contributions! Please see our [contributing guidelines](../README.md#-contributing) for details.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Qwen3-VL](https://github.com/QwenLM/Qwen-VL) for the powerful vision-language model
- [Django](https://www.djangoproject.com/) for the robust web framework
- [Bootstrap](https://getbootstrap.com/) for the responsive UI components
- [LlamaCpp](https://github.com/ggml-org/llama.cpp) for local inference capabilities
- All contributors who help improve this project

---

## 📥 Installation

### Quick Start with Docker

```bash
# Clone the repository
git clone https://github.com/faisalthaheem/open-lpr.git
cd open-lpr

# Copy environment file
cp .env.example .env

# Edit the environment file with your configuration
nano .env

# Run with Docker Compose
docker-compose up -d
```

### Quick Start with LlamaCpp (CPU)

```bash
# Clone the repository
git clone https://github.com/faisalthaheem/open-lpr.git
cd open-lpr

# Copy LlamaCpp environment file
cp .env.llamacpp.example .env.llamacpp

# Edit the environment file with your HuggingFace token
nano .env.llamacpp

# Run with Docker Compose
docker-compose -f docker-compose-llamacpp-cpu.yml up -d
```

For more detailed installation instructions, see the [README](../README.md).

---

**Thank you for using Open LPR!** 🎉

If you encounter any issues or have questions, please [file an issue](https://github.com/faisalthaheem/open-lpr/issues) on GitHub.