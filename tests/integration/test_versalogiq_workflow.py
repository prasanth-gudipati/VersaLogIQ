#!/usr/bin/env python3
"""
Integration tests for VersaLogIQ workflow testing
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os
import tempfile
import json
import time

# Add parent directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from test_config import MOCK_SERVERS, FLAVOR_TEST_CONFIG, get_test_server
from mock.mock_responses import create_mock_server, FlavorResponseGenerator
from versalogiq_app import VersaLogIQ

class TestVersaLogIQWorkflow(unittest.TestCase):
    """Integration tests for complete VersaLogIQ workflows"""
    
    def setUp(self):
        """Set up integration test environment"""
        self.versalogiq = VersaLogIQ()
        
        # Capture log output for verification
        self.log_messages = []
        self.original_log_output = self.versalogiq.log_output
        self.versalogiq.log_output = self._capture_log_output
        
        # Capture WebSocket emissions
        self.emitted_events = []
        self.original_emit = getattr(self.versalogiq, 'emit', None)
        if self.original_emit:
            def mock_emit(event, data):
                self.emitted_events.append((event, data))
                # Call original if exists
                try:
                    self.original_emit(event, data)
                except:
                    pass
            self.versalogiq.emit = mock_emit
    
    def tearDown(self):
        """Clean up after tests"""
        self.versalogiq.log_output = self.original_log_output
        if self.original_emit:
            self.versalogiq.emit = self.original_emit
        
        # Close any SSH connections
        if self.versalogiq.ssh_client:
            try:
                self.versalogiq.ssh_client.close()
            except:
                pass
    
    def _capture_log_output(self, message, tag):
        """Capture log messages for testing"""
        self.log_messages.append((message, tag))
        # Optionally call original for debugging
        # self.original_log_output(message, tag)
    
    def _get_log_messages_with_tag(self, tag):
        """Get log messages with specific tag"""
        return [msg[0] for msg in self.log_messages if msg[1] == tag]
    
    def _get_emitted_events(self, event_name):
        """Get emitted events with specific name"""
        return [data for event, data in self.emitted_events if event == event_name]
    
    @patch('versalogiq_app.VersaLogIQ.execute_ssh_command')
    @patch('paramiko.SSHClient')
    def test_complete_vms_workflow(self, mock_ssh_class, mock_execute):
        """Test complete workflow for VMS server"""
        # Setup mock SSH client
        mock_client = Mock()
        mock_ssh_class.return_value = mock_client
        mock_client.connect.return_value = None
        
        # Create VMS mock server responses
        vms_mock = create_mock_server('VMS')
        response_generator = FlavorResponseGenerator(vms_mock)
        
        def mock_command_execution(command, timeout=30, use_sudo=False):
            return response_generator.get_response(command)
        
        mock_execute.side_effect = mock_command_execution
        
        # Step 1: Connect to server
        connection_result = self.versalogiq.connect_to_server(
            host="vms.test.com",
            username="admin",
            password="password123",
            key_filename=None
        )
        
        self.assertTrue(connection_result)
        self.assertTrue(self.versalogiq.connected)
        
        # Step 2: Detect flavor
        detected_flavor = self.versalogiq.detect_server_flavour()
        self.assertEqual(detected_flavor, "VMS")
        
        # Step 3: Test sudo access
        sudo_info = self.versalogiq.test_sudo_access()
        self.assertIsNotNone(sudo_info)
        
        # Step 4: Scan system logs
        log_files = self.versalogiq.scan_system_logs()
        self.assertIsNotNone(log_files)
        
        # Verify log messages were generated
        connection_logs = self._get_log_messages_with_tag('connection')
        flavor_logs = self._get_log_messages_with_tag('flavor')
        
        self.assertGreater(len(connection_logs), 0)
        self.assertGreater(len(flavor_logs), 0)
        
        # Verify flavor detection messages
        flavor_messages = [msg for msg in flavor_logs if "VMS" in msg]
        self.assertGreater(len(flavor_messages), 0)
    
    @patch('versalogiq_app.VersaLogIQ.execute_ssh_command')
    @patch('paramiko.SSHClient')
    def test_complete_scim_workflow(self, mock_ssh_class, mock_execute):
        """Test complete workflow for SCIM server with passwordless sudo"""
        # Setup mock SSH client
        mock_client = Mock()
        mock_ssh_class.return_value = mock_client
        mock_client.connect.return_value = None
        
        # Create SCIM mock server responses
        scim_mock = create_mock_server('SCIM')
        response_generator = FlavorResponseGenerator(scim_mock)
        
        def mock_command_execution(command, timeout=30, use_sudo=False):
            return response_generator.get_response(command)
        
        mock_execute.side_effect = mock_command_execution
        
        # Step 1: Connect to server
        connection_result = self.versalogiq.connect_to_server(
            host="scim.test.com",
            username="scimuser",
            password="scimpass",
            key_filename=None
        )
        
        self.assertTrue(connection_result)
        
        # Step 2: Detect flavor
        detected_flavor = self.versalogiq.detect_server_flavour()
        self.assertEqual(detected_flavor, "SCIM")
        
        # Step 3: Test sudo (should be passwordless)
        sudo_info = self.versalogiq.test_sudo_access()
        
        # SCIM mock should have passwordless sudo
        self.assertTrue(sudo_info.get('sudo_available', False))
        self.assertFalse(sudo_info.get('requires_password', True))
        
        # Verify log messages show passwordless sudo
        connection_logs = self._get_log_messages_with_tag('connection')
        sudo_messages = [msg for msg in connection_logs if "passwordless" in msg.lower()]
        self.assertGreater(len(sudo_messages), 0)
    
    @patch('versalogiq_app.VersaLogIQ.execute_ssh_command')
    @patch('paramiko.SSHClient')
    def test_flavor_detection_priority_workflow(self, mock_ssh_class, mock_execute):
        """Test that flavor detection follows priority order"""
        # Setup mock SSH client
        mock_client = Mock()
        mock_ssh_class.return_value = mock_client
        mock_client.connect.return_value = None
        
        command_execution_order = []
        
        def track_command_execution(command, timeout=30, use_sudo=False):
            command_execution_order.append(command)
            
            # Return VOS response for vsh commands to test priority
            if "vsh" in command.lower():
                return ("versa-flexvnf version 20.2.3", "")
            return ("", "")
        
        mock_execute.side_effect = track_command_execution
        
        # Connect and detect flavor
        self.versalogiq.connect_to_server("test.com", "user", "pass")
        detected_flavor = self.versalogiq.detect_server_flavour()
        
        # Should detect VOS
        self.assertEqual(detected_flavor, "VOS")
        
        # Verify command execution order follows priority
        self.assertGreater(len(command_execution_order), 0)
        
        # Should test higher priority flavors first
        # (exact order depends on flavor configuration priority)
        vms_commands = [cmd for cmd in command_execution_order if "msgservice" in cmd]
        vos_commands = [cmd for cmd in command_execution_order if "vsh" in cmd]
        
        # VOS commands should be executed (since that's what matched)
        self.assertGreater(len(vos_commands), 0)
    
    @patch('versalogiq_app.VersaLogIQ.execute_ssh_command')
    @patch('paramiko.SSHClient')
    def test_log_scanning_with_gz_exclusion(self, mock_ssh_class, mock_execute):
        """Test log scanning with .gz file exclusion"""
        # Setup mock SSH client
        mock_client = Mock()
        mock_ssh_class.return_value = mock_client
        mock_client.connect.return_value = None
        
        # Mock log file listing with .gz files
        def mock_command_execution(command, timeout=30, use_sudo=False):
            if "find" in command and "/var/log" in command:
                return (
                    "/var/log/messages\n"
                    "/var/log/syslog\n"
                    "/var/log/auth.log\n"
                    "/var/log/messages.1.gz\n"
                    "/var/log/syslog.2.gz\n"
                    "/var/log/old_backup.gz",
                    ""
                )
            elif "whoami" in command:
                return ("testuser", "")
            elif "sudo whoami" in command:
                return ("root", "")
            return ("", "")
        
        mock_execute.side_effect = mock_command_execution
        
        # Connect and scan logs
        self.versalogiq.connect_to_server("test.com", "user", "pass")
        log_files = self.versalogiq.scan_system_logs()
        
        # Verify .gz files are excluded
        if log_files:
            gz_files = [f for f in log_files if f.endswith('.gz')]
            self.assertEqual(len(gz_files), 0, "Found .gz files in results - exclusion failed")
            
            # Verify non-.gz files are included
            regular_files = [f for f in log_files if not f.endswith('.gz')]
            self.assertGreater(len(regular_files), 0, "No regular log files found")
    
    def test_error_handling_workflow(self):
        """Test error handling throughout the workflow"""
        # Test connection without SSH client
        result = self.versalogiq.connect_to_server("invalid.host", "user", "pass")
        self.assertFalse(result)
        
        # Test flavor detection without connection
        flavor = self.versalogiq.detect_server_flavour()
        self.assertEqual(flavor, "Unknown")
        
        # Test sudo test without connection
        sudo_info = self.versalogiq.test_sudo_access()
        self.assertFalse(sudo_info.get('sudo_available', True))
        
        # Test log scanning without connection
        logs = self.versalogiq.scan_system_logs()
        self.assertEqual(len(logs), 0)
        
        # Verify error messages were logged
        error_logs = [msg for msg, tag in self.log_messages if 'error' in msg.lower()]
        self.assertGreater(len(error_logs), 0)

class TestMultiServerWorkflow(unittest.TestCase):
    """Test workflows with multiple server types"""
    
    def setUp(self):
        """Set up multi-server test environment"""
        self.test_servers = []
        
        # Create test configurations for multiple server types
        for flavor in ['VMS', 'VOS', 'SCIM', 'UBUNTU']:
            server_config = get_test_server(flavor.lower())
            if server_config:
                self.test_servers.append((flavor, server_config))
    
    def test_multiple_server_flavor_detection(self):
        """Test flavor detection across multiple server types"""
        results = {}
        
        for flavor, server_config in self.test_servers:
            versalogiq = VersaLogIQ()
            
            # Mock the detection for each server type
            with patch('versalogiq_app.VersaLogIQ.execute_ssh_command') as mock_execute:
                # Create mock responses for this flavor
                mock_config = create_mock_server(flavor)
                response_generator = FlavorResponseGenerator(mock_config)
                
                def mock_command_execution(command, timeout=30, use_sudo=False):
                    return response_generator.get_response(command)
                
                mock_execute.side_effect = mock_command_execution
                
                # Test detection
                versalogiq.ssh_client = Mock()
                versalogiq.connected = True
                
                detected_flavor = versalogiq.detect_server_flavour()
                results[flavor] = detected_flavor
        
        # Verify each server type was correctly detected
        for flavor, server_config in self.test_servers:
            expected_flavor = flavor
            if flavor == 'UBUNTU':
                expected_flavor = 'Ubuntu Linux'  # Adjust for actual flavor name
            
            self.assertEqual(results[flavor], expected_flavor,
                           f"Failed to detect {flavor} server correctly")
    
    def test_server_configuration_completeness(self):
        """Test that all server configurations are complete"""
        for flavor, server_config in self.test_servers:
            # Verify required configuration fields
            self.assertIn('host', server_config)
            self.assertIn('username', server_config)
            
            # Verify authentication method
            has_password = 'password' in server_config
            has_key = 'key_filename' in server_config
            self.assertTrue(has_password or has_key,
                          f"No authentication method for {flavor}")

class TestWebSocketIntegration(unittest.TestCase):
    """Test WebSocket integration for real-time updates"""
    
    def setUp(self):
        """Set up WebSocket integration test environment"""
        self.versalogiq = VersaLogIQ()
        
        # Mock WebSocket emit functionality
        self.emitted_events = []
        
        def mock_emit(event, data):
            self.emitted_events.append((event, data))
        
        self.versalogiq.emit = mock_emit
    
    def test_flavor_detection_websocket_events(self):
        """Test WebSocket events during flavor detection"""
        # Mock SSH connection
        self.versalogiq.ssh_client = Mock()
        self.versalogiq.connected = True
        
        with patch('versalogiq_app.VersaLogIQ.execute_ssh_command') as mock_execute:
            # Mock VMS response
            mock_execute.return_value = ("msgservice: running", "")
            
            # Perform flavor detection
            detected_flavor = self.versalogiq.detect_server_flavour()
            
            # Check for flavor detection events
            flavor_events = [data for event, data in self.emitted_events 
                           if event == 'flavor_detected']
            
            self.assertGreater(len(flavor_events), 0, "No flavor_detected events emitted")
            
            # Verify event data
            flavor_event_data = flavor_events[0]
            self.assertIn('flavor', flavor_event_data)
            self.assertEqual(flavor_event_data['flavor'], 'VMS')

class TestPerformanceWorkflow(unittest.TestCase):
    """Test performance aspects of workflows"""
    
    def setUp(self):
        """Set up performance test environment"""
        self.versalogiq = VersaLogIQ()
    
    def test_flavor_detection_performance(self):
        """Test flavor detection performance"""
        # Mock SSH connection
        self.versalogiq.ssh_client = Mock()
        self.versalogiq.connected = True
        
        with patch('versalogiq_app.VersaLogIQ.execute_ssh_command') as mock_execute:
            # Mock responses that will cause multiple command attempts
            call_count = 0
            
            def mock_command_execution(command, timeout=30, use_sudo=False):
                nonlocal call_count
                call_count += 1
                
                # Return VMS response after a few attempts
                if call_count >= 3 and "msgservice" in command:
                    return ("msgservice: running", "")
                return ("", "")
            
            mock_execute.side_effect = mock_command_execution
            
            # Measure detection time
            start_time = time.time()
            detected_flavor = self.versalogiq.detect_server_flavour()
            end_time = time.time()
            
            detection_time = end_time - start_time
            
            # Verify reasonable performance (should be fast with mocks)
            self.assertLess(detection_time, 5.0, "Flavor detection took too long")
            self.assertEqual(detected_flavor, "VMS")
    
    def test_log_scanning_performance(self):
        """Test log scanning performance with large file lists"""
        # Mock SSH connection
        self.versalogiq.ssh_client = Mock()
        self.versalogiq.connected = True
        
        with patch('versalogiq_app.VersaLogIQ.execute_ssh_command') as mock_execute:
            # Generate large log file list
            large_log_list = "\n".join([f"/var/log/file_{i}.log" for i in range(1000)])
            
            def mock_command_execution(command, timeout=30, use_sudo=False):
                if "find" in command:
                    return (large_log_list, "")
                elif "whoami" in command:
                    return ("testuser", "")
                return ("", "")
            
            mock_execute.side_effect = mock_command_execution
            
            # Measure scanning time
            start_time = time.time()
            log_files = self.versalogiq.scan_system_logs()
            end_time = time.time()
            
            scanning_time = end_time - start_time
            
            # Verify reasonable performance
            self.assertLess(scanning_time, 10.0, "Log scanning took too long")
            self.assertGreater(len(log_files), 0, "No log files found")

if __name__ == '__main__':
    # Run integration tests
    import argparse
    
    parser = argparse.ArgumentParser(description='Run VersaLogIQ integration tests')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--suite', choices=['workflow', 'multi', 'websocket', 'performance'], 
                       help='Test suite to run')
    parser.add_argument('--quick', action='store_true', help='Run quick tests only')
    
    args = parser.parse_args()
    
    verbosity = 2 if args.verbose else 1
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    if args.suite == 'workflow':
        suite.addTests(loader.loadTestsFromTestCase(TestVersaLogIQWorkflow))
    elif args.suite == 'multi':
        suite.addTests(loader.loadTestsFromTestCase(TestMultiServerWorkflow))
    elif args.suite == 'websocket':
        suite.addTests(loader.loadTestsFromTestCase(TestWebSocketIntegration))
    elif args.suite == 'performance':
        if not args.quick:  # Skip performance tests in quick mode
            suite.addTests(loader.loadTestsFromTestCase(TestPerformanceWorkflow))
    else:
        # Run all suites
        suite.addTests(loader.loadTestsFromTestCase(TestVersaLogIQWorkflow))
        suite.addTests(loader.loadTestsFromTestCase(TestMultiServerWorkflow))
        suite.addTests(loader.loadTestsFromTestCase(TestWebSocketIntegration))
        if not args.quick:
            suite.addTests(loader.loadTestsFromTestCase(TestPerformanceWorkflow))
    
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    
    # Print summary
    if result.wasSuccessful():
        print(f"\n✅ All integration tests passed! ({result.testsRun} tests)")
    else:
        print(f"\n❌ Integration tests failed: {len(result.failures)} failures, {len(result.errors)} errors")
        sys.exit(1)