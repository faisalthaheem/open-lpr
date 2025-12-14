#!/usr/bin/env python3
"""
Test script to verify Prometheus metrics endpoint is working
"""

import requests
import sys
import time

def test_metrics_endpoint():
    """Test the /metrics endpoint"""
    
    # Test the metrics endpoint
    metrics_url = "http://lpr.localhost/metrics/"
    
    print("Testing Prometheus metrics endpoint...")
    print(f"URL: {metrics_url}")
    
    try:
        response = requests.get(metrics_url, timeout=10)
        
        if response.status_code == 200:
            print("✅ Metrics endpoint is accessible!")
            print(f"Status Code: {response.status_code}")
            print(f"Content-Type: {response.headers.get('content-type', 'N/A')}")
            
            # Show a sample of the metrics
            metrics_content = response.text
            print(f"\n--- Sample Metrics Output ---")
            lines = metrics_content.split('\n')[:20]  # Show first 20 lines
            for line in lines:
                if line.strip() and not line.startswith('#'):
                    print(f"  {line}")
            
            if len(metrics_content.split('\n')) > 20:
                print("  ... (truncated)")
            
            print("\n--- Available Metrics ---")
            metric_names = set()
            for line in metrics_content.split('\n'):
                if line.strip() and not line.startswith('#') and '{' not in line:
                    metric_name = line.split()[0] if line.split() else ''
                    if metric_name:
                        metric_names.add(metric_name)
            
            for metric in sorted(metric_names):
                print(f"  • {metric}")
                
            return True
            
        else:
            print(f"❌ Metrics endpoint returned error: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection failed - make sure the Django app is running on localhost:8000")
        return False
    except Exception as e:
        print(f"❌ Error testing metrics endpoint: {e}")
        return False

def test_health_endpoint():
    """Test the /health/ endpoint to ensure it updates metrics"""
    
    health_url = "http://lpr.localhost/health/"
    
    print("\nTesting health endpoint (should update API metrics)...")
    
    try:
        response = requests.get(health_url, timeout=10)
        
        if response.status_code in [200, 503]:
            print(f"✅ Health endpoint responded: {response.status_code}")
            return True
        else:
            print(f"❌ Unexpected health endpoint status: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing health endpoint: {e}")
        return False

if __name__ == "__main__":
    print("🔍 Prometheus Metrics Test")
    print("=" * 40)
    
    # Test endpoints
    health_ok = test_health_endpoint()
    time.sleep(1)  # Small delay between requests
    metrics_ok = test_metrics_endpoint()
    
    print("\n" + "=" * 40)
    if health_ok and metrics_ok:
        print("🎉 All tests passed! Prometheus metrics are working.")
        sys.exit(0)
    else:
        print("❌ Some tests failed. Check the application logs.")
        sys.exit(1)
