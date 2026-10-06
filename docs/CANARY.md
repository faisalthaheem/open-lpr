# LPR Canary Monitoring System

This document describes the canary monitoring system implemented for the open-lpr application.

## Overview

The canary system monitors the end-to-end functionality of the LPR service by:
1. Posting a test image (jeep.jpg) to the LPR API every 15 minutes
2. Validating that a proper JSON response is returned
3. Monitoring response times and success rates
4. Ensuring the entire pipeline including LLM backends is working correctly

## Architecture

### Components

1. **LPR API Enhancement**: Modified `/api/v1/ocr/` endpoint to support:
   - `save_image` parameter to control image saving
   - Configurable header-based authentication for canary requests
   - Canary-specific metrics collection

2. **Canary Service**: A dedicated Python service that:
   - Runs on a configurable schedule (default: 15 minutes)
   - Posts jeep.jpg to the LPR API with proper authentication
   - Exposes Prometheus metrics for monitoring
   - Handles all edge cases and error scenarios

3. **Monitoring Stack**: Prometheus + Grafana for:
   - Metrics collection and storage
   - Dashboard visualization
   - Alerting capabilities

## Configuration

### Environment Variables

Add these to your `.env` file:

```bash
# Canary Configuration
CANARY_HEADER_NAME=X-Canary-Request
CANARY_HEADER_VALUE=my-secret-token-2024
CANARY_ENABLED=true
CANARY_INTERVAL=900  # 15 minutes in seconds
```

### Security

The canary system uses header-based authentication:
- Only requests with the correct header value can use `save_image=false`
- This prevents external users from bypassing image saving
- Header values are configurable for security rotation

## Deployment

### Docker Compose

The canary service is included in the main docker-compose.yml:

```bash
# Start with canary included
docker-compose --profile core up -d

# View canary logs
docker-compose logs -f lpr-canary

# Access canary metrics
curl http://localhost:9100/metrics
```

### Services

- **lpr-canary**: Main canary service (port 9100)
- **blackbox-exporter**: Additional HTTP monitoring (port 9115)
- **prometheus**: Metrics collection (port 9090)
- **grafana**: Dashboard visualization (port 3000)

## Monitoring

### Grafana Dashboard

Access the canary dashboard at:
- URL: http://grafana.localhost (or http://localhost:3000)
- Dashboard: "LPR Canary Dashboard"
- Metrics include:
  - Request rate by status (success/failed/error)
  - Response time percentiles (50th, 95th, 99th)
  - Success rate over time
  - Total requests by status

### Prometheus Metrics

Key metrics exposed by the canary service:

- `lpr_canary_script_requests_total{status}` - Total requests by status
- `lpr_canary_script_duration_seconds_bucket` - Response time histogram
- `lpr_canary_requests_total{status}` - API-side canary metrics
- `lpr_canary_processing_duration_seconds` - API-side processing time

## API Changes

### New Parameters

The `/api/v1/ocr/` endpoint now supports:

```bash
# Standard request (saves images)
curl -X POST -F "image=@test.jpg" http://localhost:8000/api/v1/ocr/

# Canary request (doesn't save images)
curl -X POST \
  -H "X-Canary-Request: true" \
  -F "image=@test.jpg" \
  -F "save_image=false" \
  http://localhost:8000/api/v1/ocr/
```

### Response Changes

All responses now include:
```json
{
  "success": true,
  "canary_request": false,
  "image_saved": true,
  // ... other fields
}
```

## Testing

### Manual Canary Test

```bash
# Test the canary endpoint manually
curl -X POST \
  -H "X-Canary-Request: true" \
  -F "image=@canary-imgs/jeep.jpg" \
  -F "save_image=false" \
  http://localhost:8000/api/v1/ocr/
```

### Integration Testing

1. Start the full stack: `docker-compose --profile core up -d`
2. Wait for services to be ready (check health endpoints)
3. Monitor canary logs: `docker-compose logs -f lpr-canary`
4. Check Grafana dashboard for metrics
5. Verify canary requests appear in LPR logs

## Troubleshooting

### Common Issues

1. **Canary not making requests**:
   - Check environment variables in docker-compose.yml
   - Verify LPR API is accessible from canary container
   - Check canary logs for errors

2. **Authentication failures**:
   - Ensure `CANARY_HEADER_VALUE` matches between canary and LPR app
   - Check that header name is correct (`X-Canary-Request` by default)

3. **Metrics not appearing**:
   - Verify Prometheus is scraping canary service (port 9100)
   - Check Prometheus targets page: http://localhost:9090/targets
   - Ensure Grafana dashboard is imported correctly

### Logs

```bash
# View canary service logs
docker-compose logs -f lpr-canary

# View LPR app logs (look for canary requests)
docker-compose logs -f lpr-app | grep "Canary"

# View Prometheus logs
docker-compose logs -f prometheus
```

## Security Considerations

1. **Header Authentication**: Only internal canary requests can bypass image saving
2. **Configurable Tokens**: Header values can be rotated without code changes
3. **Network Isolation**: All communication stays within Docker network
4. **Audit Logging**: All canary requests are logged for security review

## Customization

### Changing Test Image

1. Replace `canary/jeep.jpg` with your test image
2. Rebuild canary service: `docker-compose build lpr-canary`
3. Restart service: `docker-compose restart lpr-canary`

### Adjusting Schedule

Modify `CANARY_INTERVAL` in docker-compose.yml or environment:
```yaml
environment:
  - CANARY_INTERVAL=300  # 5 minutes
```

### Adding New Metrics

Extend `canary/canary.py` to add custom Prometheus metrics for your specific needs.

## Future Enhancements

- Alertmanager integration for notifications
- Multiple test images for better coverage
- Performance regression detection
- Automated response to canary failures
- Integration with CI/CD pipelines
