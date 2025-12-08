# LlamaCpp and ROCm Resources

This document contains important URLs and resources for deploying OpenLPR with LlamaCpp and ROCm support.

## ROCm Docker Deployment

### [ROCm Docker Installation Guide](https://rocm.docs.amd.com/projects/install-on-linux/en/latest/how-to/docker.html#docker-compose)
**Relevance**: Official AMD documentation for setting up ROCm with Docker and Docker Compose. Essential for GPU-accelerated deployment of LlamaCpp on AMD hardware.

## LlamaCpp Documentation

### [LlamaCpp Multimodal Support](https://github.com/ggml-org/llama.cpp/blob/master/docs/multimodal.md)
**Relevance**: Comprehensive documentation for using multimodal models (like Qwen3-VL) with LlamaCpp. Covers vision-language model setup, configuration, and usage patterns.

### [LlamaCpp Server Documentation](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
**Relevance**: Detailed guide for the LlamaCpp server component, which provides OpenAI-compatible API endpoints. Critical for understanding server configuration, API endpoints, and deployment options.

### [LlamaCpp Docker Deployment](https://github.com/ggml-org/llama.cpp/blob/master/docs/docker.md)
**Relevance**: Official Docker deployment documentation for LlamaCpp, including container configuration, environment variables, and best practices for containerized deployments.

### [LlamaCpp DevOps Resources](https://github.com/ggml-org/llama.cpp/tree/master/.devops)
**Relevance**: Development and operations resources including CI/CD configurations, build scripts, and deployment automation tools for LlamaCpp.

## Model Resources

### [Qwen3-VL-4B Multimodal Projector](https://huggingface.co/unsloth/Qwen3-VL-4B-Instruct-GGUF/blob/main/mmproj-BF16.gguf)
**Relevance**: The multimodal projector file required for vision-language processing with Qwen3-VL models in GGUF format. Essential for image understanding capabilities.

### [Qwen3-VL-4B Model Repository](https://huggingface.co/unsloth/Qwen3-VL-4B-Instruct-GGUF/tree/main)
**Relevance**: Complete model repository containing all necessary files for Qwen3-VL-4B in GGUF format. Includes various quantization levels and model variants for different hardware configurations.

## Usage Notes

### ROCm-Specific Considerations
- ROCm provides GPU acceleration for AMD Radeon GPUs
- Requires compatible AMD hardware and drivers
- Offers significant performance improvements over CPU-only inference

### Model Selection
- Q4_K_M: Balanced quality and performance (recommended for most use cases)
- Q5_K_M: Higher quality with moderate performance impact
- BF16: Highest quality for multimodal projector (mmproj file)

### Deployment Architecture
- LlamaCpp server provides OpenAI-compatible API endpoints
- OpenLPR connects to local LlamaCpp instance instead of cloud APIs
- Docker Compose orchestrates both services in a unified deployment

## Additional Resources

For more information about OpenLPR deployment with LlamaCpp:
- [README-llamacpp.md](../README-llamacpp.md) - Comprehensive deployment guide
- [docker-compose-llamacpp-cpu.yml](../docker-compose-llamacpp-cpu.yml) - CPU-based Docker Compose configuration
- [docker-compose-llamacpp-amd-vulcan.yml](../docker-compose-llamacpp-amd-vulcan.yml) - AMD Vulkan GPU Docker Compose configuration
- [DOCKER_DEPLOYMENT.md](../DOCKER_DEPLOYMENT.md) - General Docker deployment documentation