## 1. Add Health Checks

- [x] 1.1 Add health check to `prometheus` service using `wget --spider --quiet http://localhost:9090/-/healthy`.
- [x] 1.2 Add health check to `grafana` service using `wget --spider --quiet http://localhost:3000/api/health`.
- [x] 1.3 Add health check to `blackbox-exporter` service using `wget --spider --quiet http://localhost:9115`.
- [x] 1.4 Add health check to `lpr-canary` service using `wget --spider --quiet http://localhost:9100/metrics`.
