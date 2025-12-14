# Prometheus Metrics for Open LPR Application

This document describes the Prometheus metrics implemented for monitoring the Open LPR (License Plate Recognition) application.

## Overview

The Open LPR application now exposes comprehensive Prometheus metrics at the `/metrics/` endpoint. These metrics provide insights into application performance, business KPIs, system health, and error tracking.

## Available Metrics

### 🚀 Application Performance Metrics

#### `lpr_processing_duration_seconds`
- **Type**: Histogram
- **Description**: Time spent processing images through the LPR pipeline
- **Labels**: `status` (completed, failed, error)
- **Buckets**: [0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 25.0, 50.0, +Inf]

#### `lpr_api_request_duration_seconds`
- **Type**: Histogram
- **Description**: Time spent calling external AI API (Qwen3-VL)
- **Buckets**: [0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 25.0, +Inf]

### 📊 Business Metrics

#### `lpr_upload_total`
- **Type**: Counter
- **Description**: Total number of image uploads
- **Labels**: `status` (success, failed, error)

#### `lpr_processing_total`
- **Type**: Counter
- **Description**: Total number of image processing operations
- **Labels**: `status` (completed, failed, error)

#### `lpr_plates_detected_total`
- **Type**: Counter
- **Description**: Total number of license plates detected across all images

#### `lpr_ocr_texts_detected_total`
- **Type**: Counter
- **Description**: Total number of OCR text extractions from license plates

#### `lpr_detection_accuracy`
- **Type**: Gauge
- **Description**: Average confidence score for detection results (0.0 to 1.0)

### 🏥 System Health Metrics

#### `lpr_images_in_storage`
- **Type**: Gauge
- **Description**: Total number of images currently stored in the system

#### `lpr_processing_queue_size`
- **Type**: Gauge
- **Description**: Number of images currently pending processing

#### `lpr_database_connections_active`
- **Type**: Gauge
- **Description**: Number of active database connections

#### `lpr_file_storage_size_bytes`
- **Type**: Gauge
- **Description**: Total size of file storage in bytes

#### `lpr_api_health_status`
- **Type**: Gauge
- **Description**: Health status of external API (1=healthy, 0=unhealthy)

### ❌ Error Metrics

#### `lpr_processing_errors_total`
- **Type**: Counter
- **Description**: Total number of processing errors
- **Labels**: `error_type` (processing_failed, exception)

#### `lpr_api_errors_total`
- **Type**: Counter
- **Description**: Total number of external API errors
- **Labels**: `error_type` (api_call_failed, timeout, etc.)

#### `lpr_file_errors_total`
- **Type**: Counter
- **Description**: Total number of file operation errors
- **Labels**: `error_type` (file_not_found, permission_denied, etc.)

## Usage Examples

### Grafana Dashboard Queries

#### Processing Performance
```promql
# Average processing time
rate(lpr_processing_duration_seconds_sum[5m]) / rate(lpr_processing_duration_seconds_count[5m])

# Processing success rate
sum(rate(lpr_processing_total{status="completed"}[5m])) / sum(rate(lpr_processing_total[5m]))
```

#### Business KPIs
```promql
# Plates detected per minute
rate(lpr_plates_detected_total[5m])

# OCR texts detected per minute
rate(lpr_ocr_texts_detected_total[5m])

# Current detection accuracy
lpr_detection_accuracy
```

#### System Health
```promql
# API health status
lpr_api_health_status

# Processing queue size
lpr_processing_queue_size

# Storage usage
lpr_file_storage_size_bytes / (1024*1024*1024)  # in GB
```

### Alerting Rules

Example Prometheus alerting rules:

```yaml
groups:
  - name: lpr_app
    rules:
      - alert: HighProcessingTime
        expr: histogram_quantile(0.95, rate(lpr_processing_duration_seconds_bucket[5m])) > 10
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High image processing time detected"
          
      - alert: ProcessingQueueBacklog
        expr: lpr_processing_queue_size > 10
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Processing queue is backing up"
          
      - alert: APIDown
        expr: lpr_api_health_status == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "External AI API is unhealthy"
```

## Configuration

### Prometheus Configuration

The metrics endpoint is already configured in `prometheus/prometheus.yml`:

```yaml
  - job_name: 'lpr-app'
    static_configs:
      - targets: ['lpr-app:8000']
    metrics_path: /metrics
    scrape_interval: 15s
```

### Docker Setup

The metrics endpoint is accessible when running the application with Docker:

```bash
# Start the application
docker-compose up -d

# Access metrics locally
curl http://localhost:8000/metrics/

# Test with the provided script
python test_metrics.py
```

## Testing

A test script is provided to verify the metrics implementation:

```bash
python test_metrics.py
```

This script will:
1. Test the health endpoint (which updates API metrics)
2. Test the metrics endpoint
3. Display available metrics
4. Show sample metric values

## Implementation Details

### Files Modified

1. **`requirements.txt`** - Added `prometheus-client==0.19.0`
2. **`lpr_app/metrics.py`** - New file defining all Prometheus metrics
3. **`lpr_app/views.py`** - Added metric collection to key functions
4. **`lpr_app/urls.py`** - Added `/metrics/` endpoint

### Key Instrumentation Points

- **Image Upload**: Tracks upload success/failure rates
- **Processing Pipeline**: Measures duration and success rates
- **API Calls**: Monitors external AI API health and response times
- **Business Logic**: Counts plates detected and OCR extractions
- **System Health**: Monitors database, storage, and queue status
- **Error Handling**: Categorizes and counts different error types

### Performance Considerations

- Metrics collection is designed to be non-blocking
- Failed metric updates won't crash the application
- System metrics are calculated efficiently
- Storage size calculation may be optimized in production

## Security

The `/metrics/` endpoint is publicly accessible. In production environments, consider:

1. Restricting access to monitoring systems only
2. Using authentication headers for metrics scraping
3. Rate limiting the metrics endpoint

## Troubleshooting

### Common Issues

1. **Metrics Not Updating**
   - Check Django application logs for errors
   - Verify the application is receiving traffic
   - Ensure metric collection code is being executed

2. **High Memory Usage**
   - Storage size calculation walks the media directory
   - Consider optimizing for large deployments

3. **Missing Metrics**
   - Restart the application after code changes
   - Check Prometheus configuration
   - Verify metric endpoint accessibility

### Debug Commands

```bash
# Check metrics endpoint directly
curl -s http://localhost:8000/metrics/ | head -20

# Test specific metric extraction
curl -s http://localhost:8000/metrics/ | grep lpr_processing_duration

# Check health endpoint (updates API metrics)
curl -s http://localhost:8000/health/
```

## Future Enhancements

Potential improvements to the metrics implementation:

1. **Per-User Metrics**: Track usage by user/API key
2. **Model-Specific Metrics**: Monitor different AI model performance
3. **Resource Usage**: CPU, memory, and GPU utilization
4. **Cache Metrics**: Hit rates for cached results
5. **Custom Labels**: Add more granular categorization

## Support

For issues or questions about the metrics implementation:

1. Check the Django application logs
2. Review this documentation
3. Test with the provided test script
4. Verify Prometheus configuration

The metrics implementation follows Prometheus best practices and provides comprehensive monitoring coverage for the Open LPR application.
