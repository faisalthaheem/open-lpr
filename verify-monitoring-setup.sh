#!/bin/bash

echo "=== LPR Monitoring Setup Verification ==="
echo

# Check if prometheus config is valid
echo "1. Checking Prometheus configuration..."
if timeout 5s docker run --rm -v $(pwd)/prometheus:/etc/prometheus prom/prometheus:latest --config.file=/etc/prometheus/prometheus.yml 2>/dev/null | grep -q "Starting Prometheus Server"; then
    echo "✅ Prometheus configuration is valid"
else
    echo "❌ Prometheus configuration has errors"
fi

# Check if Grafana dashboard JSON is valid
echo "2. Checking Grafana dashboard JSON..."
if python3 -m json.tool grafana/provisioning/dashboards/lpr-app-dashboard.json > /dev/null 2>&1; then
    echo "✅ Grafana dashboard JSON is valid"
else
    echo "❌ Grafana dashboard JSON has errors"
fi

# Show current prometheus targets
echo "3. Current Prometheus scrape targets:"
echo "   - prometheus (localhost:9090)"
echo "   - lpr-app (lpr-app:8000)"
echo "   Removed: traefik, node-exporter, cadvisor, grafana"
echo

# Show dashboard metrics
echo "4. Dashboard includes these LPR metrics:"
echo "   - Request Rates: upload_total, processing_total"
echo "   - Detection Totals: plates_detected, ocr_texts_detected"
echo "   - Performance: processing duration percentiles"
echo "   - Health: detection accuracy, API health status"
echo "   - Storage: images in storage, file size, DB connections"
echo "   - Errors: processing, API, and file error rates"
echo

echo "=== Setup Complete ==="
echo "To apply changes:"
echo "1. Restart services: docker-compose down && docker-compose up -d"
echo "2. Access Grafana: http://grafana.localhost (admin/admin)"
echo "3. Access Prometheus: http://prometheus.localhost"
