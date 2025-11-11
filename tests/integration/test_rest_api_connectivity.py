#!/usr/bin/env python3
"""
REST API connectivity tests for VersaLogIQ servers
"""

import unittest
import requests
import json
import time
import threading
from unittest.mock import Mock, patch
import sys
import os
from pathlib import Path

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'backend'))
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from test_config import get_test_server, API_TEST_CONFIG
except ImportError:
    # Fallback if test_config not available
    def get_test_server(flavor):
        return None
    API_TEST_CONFIG = {
        'base_url': 'http://localhost:5000',
        'timeout': {'default': 10}
    }

try:
    from mock.mock_responses import create_mock_server
except ImportError:
    def create_mock_server(flavor):
        return {'flavor': flavor, 'responses': {}}

class TestRESTAPIConnectivity(unittest.TestCase):
    """Test REST API connectivity to servers from ssh_hosts.json"""
    
    def setUp(self):
        """Set up test environment"""
        self.base_url = "http://localhost:5000"
        self.ssh_hosts_file = Path(__file__).parent.parent / "ssh_hosts.json"
        
        # Load SSH hosts configuration
        self.servers = self.load_ssh_hosts()
        
        # Test timeout settings
        self.timeout = 10
        self.connection_timeout = 30
        
    def load_ssh_hosts(self):
        """Load servers from ssh_hosts.json"""
        try:
            with open(self.ssh_hosts_file, 'r') as f:
                data = json.load(f)
                return data.get('hosts', [])
        except FileNotFoundError:
            self.skipTest(f"SSH hosts file not found: {self.ssh_hosts_file}")
        except json.JSONDecodeError as e:
            self.skipTest(f"Invalid JSON in SSH hosts file: {e}")
    
    def test_api_health_check(self):
        """Test basic API health check endpoint"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=self.timeout)
            
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data['status'], 'healthy')
            self.assertEqual(data['service'], 'VersaLogIQ')
            
        except requests.exceptions.ConnectionError:
            self.skipTest("VersaLogIQ server not running")
    
    def test_api_version_endpoint(self):
        """Test API version endpoint"""
        try:
            response = requests.get(f"{self.base_url}/version", timeout=self.timeout)
            
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn('service', data)
            self.assertIn('version', data)
            self.assertIn('features', data)
            
        except requests.exceptions.ConnectionError:
            self.skipTest("VersaLogIQ server not running")

class TestServerConnectivityAPI(unittest.TestCase):
    """Test API endpoints for server connectivity checking"""
    
    def setUp(self):
        """Set up server connectivity test environment"""
        self.base_url = "http://localhost:5000"
        self.ssh_hosts_file = Path(__file__).parent.parent / "ssh_hosts.json"
        self.servers = self.load_ssh_hosts()
        self.timeout = 15
        
        # Create API endpoints for testing (these would need to be added to the main app)
        self.api_endpoints = {
            'test_connection': f"{self.base_url}/api/test_connection",
            'check_all_servers': f"{self.base_url}/api/check_all_servers",
            'server_status': f"{self.base_url}/api/server_status",
            'connectivity_report': f"{self.base_url}/api/connectivity_report"
        }
    
    def load_ssh_hosts(self):
        """Load servers from ssh_hosts.json"""
        try:
            with open(self.ssh_hosts_file, 'r') as f:
                data = json.load(f)
                return data.get('hosts', [])
        except FileNotFoundError:
            return []
        except json.JSONDecodeError:
            return []
    
    def test_individual_server_connectivity(self):
        """Test connectivity to individual servers via API"""
        if not self.servers:
            self.skipTest("No servers configured in ssh_hosts.json")
        
        for server in self.servers:
            with self.subTest(server=server['name']):
                self._test_server_connection(server)
    
    def _test_server_connection(self, server):
        """Test connection to a specific server"""
        payload = {
            'hostname': server['hostname'],
            'username': server['user'],
            'password': server['password'],
            'expected_flavor': server['flavour']
        }
        
        try:
            # This endpoint would need to be implemented in the main application
            response = requests.post(
                self.api_endpoints['test_connection'],
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 404:
                self.skipTest("API endpoint not implemented yet")
            
            self.assertEqual(response.status_code, 200)
            data = response.json()
            
            # Verify response structure
            self.assertIn('success', data)
            self.assertIn('hostname', data)
            self.assertIn('connection_time', data)
            
            if data['success']:
                self.assertIn('detected_flavor', data)
                self.assertIn('sudo_available', data)
                
                # Verify detected flavor matches expected
                self.assertEqual(
                    data['detected_flavor'], 
                    server['flavour'],
                    f"Detected flavor {data['detected_flavor']} != expected {server['flavour']}"
                )
            
        except requests.exceptions.ConnectionError:
            self.skipTest("VersaLogIQ server not running")
    
    def test_bulk_server_connectivity(self):
        """Test connectivity to all servers via bulk API"""
        if not self.servers:
            self.skipTest("No servers configured in ssh_hosts.json")
        
        try:
            # This endpoint would check all servers in ssh_hosts.json
            response = requests.post(
                self.api_endpoints['check_all_servers'],
                timeout=60  # Longer timeout for multiple servers
            )
            
            if response.status_code == 404:
                self.skipTest("Bulk connectivity API endpoint not implemented yet")
            
            self.assertEqual(response.status_code, 200)
            data = response.json()
            
            # Verify response structure
            self.assertIn('results', data)
            self.assertIn('summary', data)
            self.assertIn('total_tested', data['summary'])
            self.assertIn('successful', data['summary'])
            self.assertIn('failed', data['summary'])
            
            # Verify all configured servers were tested
            tested_servers = {result['hostname'] for result in data['results']}
            configured_servers = {server['hostname'] for server in self.servers}
            
            self.assertEqual(tested_servers, configured_servers)
            
        except requests.exceptions.ConnectionError:
            self.skipTest("VersaLogIQ server not running")

class TestServerStatusAPI(unittest.TestCase):
    """Test API endpoints for server status monitoring"""
    
    def setUp(self):
        """Set up server status test environment"""
        self.base_url = "http://localhost:5000"
        self.ssh_hosts_file = Path(__file__).parent.parent / "ssh_hosts.json"
        self.servers = self.load_ssh_hosts()
        self.timeout = 10
    
    def load_ssh_hosts(self):
        """Load servers from ssh_hosts.json"""
        try:
            with open(self.ssh_hosts_file, 'r') as f:
                data = json.load(f)
                return data.get('hosts', [])
        except FileNotFoundError:
            return []
        except json.JSONDecodeError:
            return []
    
    def test_server_status_by_hostname(self):
        """Test getting server status by hostname"""
        if not self.servers:
            self.skipTest("No servers configured in ssh_hosts.json")
        
        for server in self.servers:
            with self.subTest(server=server['name']):
                try:
                    response = requests.get(
                        f"{self.base_url}/api/server_status/{server['hostname']}",
                        timeout=self.timeout
                    )
                    
                    if response.status_code == 404:
                        self.skipTest("Server status API endpoint not implemented yet")
                    
                    self.assertEqual(response.status_code, 200)
                    data = response.json()
                    
                    # Verify response structure
                    self.assertIn('hostname', data)
                    self.assertIn('status', data)
                    self.assertIn('last_check', data)
                    
                    self.assertEqual(data['hostname'], server['hostname'])
                    self.assertIn(data['status'], ['online', 'offline', 'unknown'])
                    
                except requests.exceptions.ConnectionError:
                    self.skipTest("VersaLogIQ server not running")
    
    def test_connectivity_report_endpoint(self):
        """Test comprehensive connectivity report endpoint"""
        try:
            response = requests.get(
                f"{self.base_url}/api/connectivity_report",
                timeout=self.timeout
            )
            
            if response.status_code == 404:
                self.skipTest("Connectivity report API endpoint not implemented yet")
            
            self.assertEqual(response.status_code, 200)
            data = response.json()
            
            # Verify report structure
            self.assertIn('generated_at', data)
            self.assertIn('servers', data)
            self.assertIn('summary', data)
            
            # Verify summary statistics
            summary = data['summary']
            self.assertIn('total_servers', summary)
            self.assertIn('online_servers', summary)
            self.assertIn('offline_servers', summary)
            self.assertIn('by_flavor', summary)
            
            # Verify flavor breakdown
            flavor_counts = summary['by_flavor']
            expected_flavors = {'VMS', 'VOS', 'SCIM', 'ECP', 'VAN'}
            
            for flavor in expected_flavors:
                if flavor in flavor_counts:
                    self.assertIsInstance(flavor_counts[flavor], dict)
                    self.assertIn('total', flavor_counts[flavor])
                    self.assertIn('online', flavor_counts[flavor])
            
        except requests.exceptions.ConnectionError:
            self.skipTest("VersaLogIQ server not running")

class TestMockServerConnectivity(unittest.TestCase):
    """Test server connectivity using mock servers for reliable testing"""
    
    def setUp(self):
        """Set up mock server testing environment"""
        self.base_url = "http://localhost:5000"
        self.timeout = 10
        
        # Mock server configurations based on ssh_hosts.json
        self.mock_servers = [
            {
                'name': 'mock-vms-server',
                'hostname': '192.168.1.100',
                'flavour': 'VMS',
                'user': 'admin',
                'password': 'test123'
            },
            {
                'name': 'mock-vos-server',
                'hostname': '192.168.1.101',
                'flavour': 'VOS',
                'user': 'admin',
                'password': 'test123'
            },
            {
                'name': 'mock-scim-server',
                'hostname': '192.168.1.102',
                'flavour': 'SCIM',
                'user': 'versa',
                'password': 'test123'
            }
        ]
    
    def test_mock_server_connectivity(self):
        """Test connectivity to mock servers"""
        for mock_server in self.mock_servers:
            with self.subTest(server=mock_server['name']):
                self._test_mock_server_connection(mock_server)
    
    def _test_mock_server_connection(self, mock_server):
        """Test connection to a mock server"""
        payload = {
            'hostname': mock_server['hostname'],
            'username': mock_server['user'],
            'password': mock_server['password'],
            'expected_flavor': mock_server['flavour'],
            'use_mock': True  # Flag to use mock responses
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/api/test_connection",
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 404:
                self.skipTest("Mock connectivity API endpoint not implemented yet")
            
            self.assertEqual(response.status_code, 200)
            data = response.json()
            
            # Verify mock response
            self.assertTrue(data['success'])
            self.assertEqual(data['hostname'], mock_server['hostname'])
            self.assertEqual(data['detected_flavor'], mock_server['flavour'])
            self.assertLessEqual(data['connection_time'], 5.0)  # Mocks should be fast
            
        except requests.exceptions.ConnectionError:
            self.skipTest("VersaLogIQ server not running")

class TestAPIPerformance(unittest.TestCase):
    """Test API performance for server connectivity operations"""
    
    def setUp(self):
        """Set up performance test environment"""
        self.base_url = "http://localhost:5000"
        self.timeout = 30
        self.performance_thresholds = {
            'single_connection': 30.0,  # seconds
            'bulk_check': 120.0,        # seconds for all servers
            'status_check': 2.0         # seconds
        }
    
    def test_single_connection_performance(self):
        """Test performance of single server connection"""
        test_server = {
            'hostname': '192.168.1.100',
            'username': 'admin',
            'password': 'test123',
            'use_mock': True
        }
        
        start_time = time.time()
        
        try:
            response = requests.post(
                f"{self.base_url}/api/test_connection",
                json=test_server,
                timeout=self.timeout
            )
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            if response.status_code == 404:
                self.skipTest("Performance test API endpoint not implemented yet")
            
            self.assertEqual(response.status_code, 200)
            self.assertLessEqual(
                execution_time, 
                self.performance_thresholds['single_connection'],
                f"Single connection took {execution_time:.2f}s, threshold: {self.performance_thresholds['single_connection']}s"
            )
            
        except requests.exceptions.ConnectionError:
            self.skipTest("VersaLogIQ server not running")
    
    def test_bulk_connectivity_performance(self):
        """Test performance of bulk connectivity check"""
        start_time = time.time()
        
        try:
            response = requests.post(
                f"{self.base_url}/api/check_all_servers",
                json={'use_mock': True},
                timeout=self.performance_thresholds['bulk_check']
            )
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            if response.status_code == 404:
                self.skipTest("Bulk performance test API endpoint not implemented yet")
            
            self.assertEqual(response.status_code, 200)
            self.assertLessEqual(
                execution_time,
                self.performance_thresholds['bulk_check'],
                f"Bulk check took {execution_time:.2f}s, threshold: {self.performance_thresholds['bulk_check']}s"
            )
            
        except requests.exceptions.ConnectionError:
            self.skipTest("VersaLogIQ server not running")

class TestAPIErrorHandling(unittest.TestCase):
    """Test API error handling for various failure scenarios"""
    
    def setUp(self):
        """Set up error handling test environment"""
        self.base_url = "http://localhost:5000"
        self.timeout = 10
    
    def test_invalid_hostname_error(self):
        """Test API response to invalid hostname"""
        payload = {
            'hostname': 'invalid.hostname.test',
            'username': 'admin',
            'password': 'test123'
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/api/test_connection",
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 404:
                self.skipTest("Error handling API endpoint not implemented yet")
            
            # Should return error response, not crash
            self.assertIn(response.status_code, [200, 400, 503])
            
            if response.status_code == 200:
                data = response.json()
                self.assertFalse(data['success'])
                self.assertIn('error', data)
            
        except requests.exceptions.ConnectionError:
            self.skipTest("VersaLogIQ server not running")
    
    def test_authentication_failure_error(self):
        """Test API response to authentication failures"""
        payload = {
            'hostname': '10.73.21.106',  # Real server from ssh_hosts.json
            'username': 'invalid_user',
            'password': 'wrong_password'
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/api/test_connection",
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 404:
                self.skipTest("Authentication error API endpoint not implemented yet")
            
            # Should handle auth failure gracefully
            self.assertIn(response.status_code, [200, 401, 403])
            
            if response.status_code == 200:
                data = response.json()
                self.assertFalse(data['success'])
                self.assertIn('error', data)
                self.assertIn('authentication', data['error'].lower())
            
        except requests.exceptions.ConnectionError:
            self.skipTest("VersaLogIQ server not running")

if __name__ == '__main__':
    # Run REST API connectivity tests
    import argparse
    
    parser = argparse.ArgumentParser(description='Run VersaLogIQ REST API connectivity tests')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--category', 
                       choices=['basic', 'connectivity', 'status', 'mock', 'performance', 'error'], 
                       help='Test category to run')
    parser.add_argument('--server', help='Test specific server hostname')
    parser.add_argument('--mock-only', action='store_true', help='Run only mock server tests')
    
    args = parser.parse_args()
    
    verbosity = 2 if args.verbose else 1
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Build test suite based on arguments
    if args.category == 'basic':
        suite.addTests(loader.loadTestsFromTestCase(TestRESTAPIConnectivity))
    elif args.category == 'connectivity':
        suite.addTests(loader.loadTestsFromTestCase(TestServerConnectivityAPI))
    elif args.category == 'status':
        suite.addTests(loader.loadTestsFromTestCase(TestServerStatusAPI))
    elif args.category == 'mock':
        suite.addTests(loader.loadTestsFromTestCase(TestMockServerConnectivity))
    elif args.category == 'performance':
        suite.addTests(loader.loadTestsFromTestCase(TestAPIPerformance))
    elif args.category == 'error':
        suite.addTests(loader.loadTestsFromTestCase(TestAPIErrorHandling))
    elif args.mock_only:
        suite.addTests(loader.loadTestsFromTestCase(TestMockServerConnectivity))
    else:
        # Run all tests
        suite.addTests(loader.loadTestsFromTestCase(TestRESTAPIConnectivity))
        suite.addTests(loader.loadTestsFromTestCase(TestServerConnectivityAPI))
        suite.addTests(loader.loadTestsFromTestCase(TestServerStatusAPI))
        if not args.server:  # Skip mock tests when testing specific server
            suite.addTests(loader.loadTestsFromTestCase(TestMockServerConnectivity))
        suite.addTests(loader.loadTestsFromTestCase(TestAPIPerformance))
        suite.addTests(loader.loadTestsFromTestCase(TestAPIErrorHandling))
    
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    
    # Print summary
    if result.wasSuccessful():
        print(f"\n✅ All REST API connectivity tests passed! ({result.testsRun} tests)")
    else:
        print(f"\n❌ REST API connectivity tests failed: {len(result.failures)} failures, {len(result.errors)} errors")
    
    # Exit with appropriate code
    exit(0 if result.wasSuccessful() else 1)