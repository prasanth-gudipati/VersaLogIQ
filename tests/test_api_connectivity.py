#!/usr/bin/env python3
"""
Simple connectivity test for VersaLogIQ REST API endpoints
"""

import requests
import json
import sys
import time
from pathlib import Path

def test_basic_endpoints(base_url="http://localhost:5000"):
    """Test basic API endpoints"""
    print("🔍 Testing Basic API Endpoints")
    print("=" * 40)
    
    # Test health endpoint
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Health endpoint: OK")
            data = response.json()
            print(f"   Status: {data.get('status')}")
        else:
            print(f"❌ Health endpoint failed: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to VersaLogIQ server")
        print("   Make sure the server is running on localhost:5000")
        return False
    except Exception as e:
        print(f"❌ Health endpoint error: {e}")
        return False
    
    # Test version endpoint
    try:
        response = requests.get(f"{base_url}/version", timeout=5)
        if response.status_code == 200:
            print("✅ Version endpoint: OK")
            data = response.json()
            print(f"   Version: {data.get('version')}")
            print(f"   Features: {len(data.get('features', []))}")
        else:
            print(f"❌ Version endpoint failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Version endpoint error: {e}")
    
    return True

def test_mock_connectivity(base_url="http://localhost:5000"):
    """Test mock server connectivity"""
    print("\n🎭 Testing Mock Server Connectivity")
    print("=" * 40)
    
    # Test mock VMS server
    test_payload = {
        "hostname": "192.168.1.100",
        "username": "admin", 
        "password": "test123",
        "expected_flavor": "VMS",
        "use_mock": True
    }
    
    try:
        response = requests.post(
            f"{base_url}/api/test_connection",
            json=test_payload,
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ Mock connection test: OK")
            data = response.json()
            print(f"   Success: {data.get('success')}")
            print(f"   Flavor: {data.get('detected_flavor')}")
            print(f"   Time: {data.get('connection_time')}s")
        elif response.status_code == 404:
            print("⚠️  Connection API endpoint not found")
            print("   The REST API endpoints may not be loaded yet")
            return False
        else:
            print(f"❌ Mock connection test failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Mock connection test error: {e}")
        return False
    
    return True

def test_real_server_connectivity(base_url="http://localhost:5000"):
    """Test connectivity to a real server from ssh_hosts.json"""
    print("\n🖥️  Testing Real Server Connectivity")
    print("=" * 40)
    
    # Load ssh_hosts.json
    ssh_hosts_file = Path(__file__).parent.parent / "ssh_hosts.json"
    
    try:
        with open(ssh_hosts_file, 'r') as f:
            hosts_data = json.load(f)
            servers = hosts_data.get('hosts', [])
    except FileNotFoundError:
        print("⚠️  ssh_hosts.json not found - skipping real server tests")
        return True
    except json.JSONDecodeError:
        print("❌ Invalid JSON in ssh_hosts.json")
        return False
    
    if not servers:
        print("⚠️  No servers configured in ssh_hosts.json")
        return True
    
    # Test first server in the list
    test_server = servers[0]
    test_payload = {
        "hostname": test_server['hostname'],
        "username": test_server['user'],
        "password": test_server['password'],
        "expected_flavor": test_server['flavour']
    }
    
    print(f"Testing connection to: {test_server['name']} ({test_server['hostname']})")
    
    try:
        response = requests.post(
            f"{base_url}/api/test_connection",
            json=test_payload,
            timeout=30  # Longer timeout for real connections
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print("✅ Real server connection: SUCCESS")
                print(f"   Detected flavor: {data.get('detected_flavor')}")
                print(f"   Expected flavor: {test_server['flavour']}")
                print(f"   Flavor match: {data.get('detected_flavor') == test_server['flavour']}")
                print(f"   Connection time: {data.get('connection_time')}s")
                print(f"   Sudo available: {data.get('sudo_available')}")
            else:
                print("❌ Real server connection: FAILED")
                print(f"   Error: {data.get('error')}")
        else:
            print(f"❌ Real server connection failed: HTTP {response.status_code}")
            print(f"   Response: {response.text}")
    
    except requests.exceptions.Timeout:
        print("⏱️  Real server connection: TIMEOUT")
        print("   This is normal if the server is unreachable")
    except Exception as e:
        print(f"❌ Real server connection error: {e}")
    
    return True

def test_bulk_connectivity(base_url="http://localhost:5000"):
    """Test bulk connectivity check"""
    print("\n📋 Testing Bulk Connectivity Check")
    print("=" * 40)
    
    # Test with mock servers
    test_payload = {"use_mock": True}
    
    try:
        response = requests.post(
            f"{base_url}/api/check_all_servers",
            json=test_payload,
            timeout=30
        )
        
        if response.status_code == 200:
            print("✅ Bulk connectivity check: OK")
            data = response.json()
            summary = data.get('summary', {})
            print(f"   Total servers: {summary.get('total_tested', 0)}")
            print(f"   Successful: {summary.get('successful', 0)}")
            print(f"   Failed: {summary.get('failed', 0)}")
            print(f"   Success rate: {summary.get('success_rate', 0)}%")
        elif response.status_code == 404:
            print("⚠️  Bulk connectivity API endpoint not found")
        else:
            print(f"❌ Bulk connectivity check failed: {response.status_code}")
            print(f"   Response: {response.text}")
    
    except Exception as e:
        print(f"❌ Bulk connectivity check error: {e}")

def test_connectivity_report(base_url="http://localhost:5000"):
    """Test connectivity report generation"""
    print("\n📊 Testing Connectivity Report")
    print("=" * 40)
    
    try:
        response = requests.get(f"{base_url}/api/connectivity_report", timeout=30)
        
        if response.status_code == 200:
            print("✅ Connectivity report: OK")
            data = response.json()
            summary = data.get('summary', {})
            print(f"   Total servers: {summary.get('total_servers', 0)}")
            print(f"   Online servers: {summary.get('online_servers', 0)}")
            print(f"   Availability: {summary.get('availability_percentage', 0)}%")
            
            # Show flavor breakdown
            by_flavor = summary.get('by_flavor', {})
            if by_flavor:
                print("   By flavor:")
                for flavor, stats in by_flavor.items():
                    print(f"     {flavor}: {stats.get('online', 0)}/{stats.get('total', 0)}")
        elif response.status_code == 404:
            print("⚠️  Connectivity report API endpoint not found")
        else:
            print(f"❌ Connectivity report failed: {response.status_code}")
    
    except Exception as e:
        print(f"❌ Connectivity report error: {e}")

def main():
    """Main test function"""
    print("🚀 VersaLogIQ REST API Connectivity Test")
    print("=" * 50)
    
    base_url = "http://localhost:5000"
    
    # Test basic endpoints first
    if not test_basic_endpoints(base_url):
        print("\n❌ Basic endpoint tests failed - server may not be running")
        sys.exit(1)
    
    # Test connectivity features
    test_mock_connectivity(base_url)
    test_real_server_connectivity(base_url)
    test_bulk_connectivity(base_url)
    test_connectivity_report(base_url)
    
    print("\n" + "=" * 50)
    print("🎉 REST API Connectivity Test Completed!")
    print("\nNext steps:")
    print("1. Run the full test suite: python run_tests.py --type integration")
    print("2. Test specific category: python test_rest_api_connectivity.py --category connectivity")
    print("3. Run with mock only: python test_rest_api_connectivity.py --mock-only")
    print("=" * 50)

if __name__ == '__main__':
    main()