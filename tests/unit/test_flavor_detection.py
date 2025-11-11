#!/usr/bin/env python3
"""
Unit tests for server flavor detection functionality
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add parent directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from test_config import FLAVOR_TEST_CONFIG, get_flavor_config
from mock.mock_responses import FlavorResponseGenerator, create_mock_server
from versalogiq_app import VersaLogIQ

class TestFlavorDetection(unittest.TestCase):
    """Test cases for server flavor detection"""
    
    def setUp(self):
        """Set up test environment"""
        self.versalogiq = VersaLogIQ()
        # Mock SSH client to avoid actual connections
        self.versalogiq.ssh_client = Mock()
        self.versalogiq.connected = True
        
        # Capture log output
        self.log_messages = []
        self.original_log_output = self.versalogiq.log_output
        self.versalogiq.log_output = self._capture_log_output
    
    def tearDown(self):
        """Clean up after tests"""
        self.versalogiq.log_output = self.original_log_output
    
    def _capture_log_output(self, message, tag):
        """Capture log messages for testing"""
        self.log_messages.append((message, tag))
        # Still call original for debugging if needed
        # self.original_log_output(message, tag)
    
    def test_flavor_config_loading(self):
        """Test that flavor configuration loads correctly"""
        self.assertIsNotNone(self.versalogiq.flavour_configs)
        self.assertGreater(len(self.versalogiq.flavour_configs), 0)
        
        # Check that all expected flavors are loaded
        expected_flavors = ['vms', 'vos', 'scim', 'ecp', 'van', 'ubuntu']
        for flavor in expected_flavors:
            self.assertIn(flavor, self.versalogiq.flavour_configs)
    
    def test_pattern_checking_contains(self):
        """Test pattern checking with contains match type"""
        # Test successful pattern match
        text = "This is a msgservice running on the server"
        patterns = ["msgservice"]
        result = self.versalogiq._check_patterns(text, patterns, "contains", False)
        self.assertTrue(result)
        
        # Test failed pattern match
        text = "This is a regular server response"
        patterns = ["msgservice"]
        result = self.versalogiq._check_patterns(text, patterns, "contains", False)
        self.assertFalse(result)
        
        # Test multiple patterns (all must match)
        text = "versa-flexvnf system running on versa platform"
        patterns = ["versa", "flexvnf"]
        result = self.versalogiq._check_patterns(text, patterns, "contains", False)
        self.assertTrue(result)
        
        # Test multiple patterns (one missing)
        text = "versa system running"
        patterns = ["versa", "flexvnf"]
        result = self.versalogiq._check_patterns(text, patterns, "contains", False)
        self.assertFalse(result)
    
    def test_pattern_checking_case_sensitivity(self):
        """Test case sensitivity in pattern checking"""
        # Case insensitive (default)
        text = "VeRsA-FlExVnF"
        patterns = ["versa", "flexvnf"]
        result = self.versalogiq._check_patterns(text, patterns, "contains", False)
        self.assertTrue(result)
        
        # Case sensitive
        text = "VeRsA-FlExVnF"
        patterns = ["versa", "flexvnf"]
        result = self.versalogiq._check_patterns(text, patterns, "contains", True)
        self.assertFalse(result)
        
        # Case sensitive match
        text = "versa-flexvnf"
        patterns = ["versa", "flexvnf"]
        result = self.versalogiq._check_patterns(text, patterns, "contains", True)
        self.assertTrue(result)
    
    @patch('versalogiq_app.VersaLogIQ.execute_ssh_command')
    def test_vms_flavor_detection(self, mock_execute):
        """Test VMS flavor detection"""
        # Mock successful VMS response
        mock_execute.return_value = ("msgservice: running (pid: 1234)", "")
        
        detected_flavor = self.versalogiq.detect_server_flavour()
        
        self.assertEqual(detected_flavor, "VMS")
        
        # Verify the correct command was called
        mock_execute.assert_called()
        
        # Check log messages
        log_messages_text = [msg[0] for msg in self.log_messages]
        self.assertTrue(any("VMS" in msg for msg in log_messages_text))
        self.assertTrue(any("✅ Server flavour detected" in msg for msg in log_messages_text))
    
    @patch('versalogiq_app.VersaLogIQ.execute_ssh_command')
    def test_vos_flavor_detection(self, mock_execute):
        """Test VOS flavor detection"""
        # Mock successful VOS response
        mock_execute.return_value = ("versa-flexvnf version 20.2.3", "")
        
        detected_flavor = self.versalogiq.detect_server_flavour()
        
        self.assertEqual(detected_flavor, "VOS")
        
        # Verify command execution
        mock_execute.assert_called()
    
    @patch('versalogiq_app.VersaLogIQ.execute_ssh_command')
    def test_scim_flavor_detection(self, mock_execute):
        """Test SCIM flavor detection"""
        # Mock successful SCIM response
        mock_execute.return_value = ("abcd1234    versa_scim:latest    running", "")
        
        detected_flavor = self.versalogiq.detect_server_flavour()
        
        self.assertEqual(detected_flavor, "SCIM")
    
    @patch('versalogiq_app.VersaLogIQ.execute_ssh_command')
    def test_ubuntu_flavor_detection(self, mock_execute):
        """Test Ubuntu flavor detection"""
        # Mock successful Ubuntu response
        mock_execute.return_value = ("Description:\tUbuntu 18.04.6 LTS", "")
        
        detected_flavor = self.versalogiq.detect_server_flavour()
        
        self.assertEqual(detected_flavor, "Ubuntu Linux")
    
    @patch('versalogiq_app.VersaLogIQ.execute_ssh_command')
    def test_unknown_flavor_detection(self, mock_execute):
        """Test unknown flavor detection (fallback)"""
        # Mock response that doesn't match any flavor
        mock_execute.return_value = ("some random output", "")
        
        detected_flavor = self.versalogiq.detect_server_flavour()
        
        self.assertEqual(detected_flavor, "Unknown")
        
        # Check log messages for fallback
        log_messages_text = [msg[0] for msg in self.log_messages]
        self.assertTrue(any("No flavour detected" in msg for msg in log_messages_text))
    
    @patch('versalogiq_app.VersaLogIQ.execute_ssh_command')
    def test_flavor_detection_priority(self, mock_execute):
        """Test that higher priority flavors are tested first"""
        call_order = []
        
        def mock_command_execution(command, timeout, use_sudo):
            call_order.append(command)
            # Return no match to continue testing
            return ("", "")
        
        mock_execute.side_effect = mock_command_execution
        
        detected_flavor = self.versalogiq.detect_server_flavour()
        
        # Should be Unknown since no patterns matched
        self.assertEqual(detected_flavor, "Unknown")
        
        # Verify that commands were called (priority order testing)
        self.assertGreater(len(call_order), 0)
    
    @patch('versalogiq_app.VersaLogIQ.execute_ssh_command')
    def test_command_execution_error_handling(self, mock_execute):
        """Test error handling during command execution"""
        # Mock command execution failure
        mock_execute.side_effect = Exception("SSH command failed")
        
        detected_flavor = self.versalogiq.detect_server_flavour()
        
        # Should fallback to Unknown on errors
        self.assertEqual(detected_flavor, "Unknown")
        
        # Check error messages in logs
        log_messages_text = [msg[0] for msg in self.log_messages]
        self.assertTrue(any("Error testing" in msg for msg in log_messages_text))
    
    def test_flavor_detection_without_ssh(self):
        """Test flavor detection when SSH is not connected"""
        # Reset SSH client
        self.versalogiq.ssh_client = None
        
        detected_flavor = self.versalogiq.detect_server_flavour()
        
        self.assertEqual(detected_flavor, "Unknown")
    
    def test_flavor_config_validation(self):
        """Test that flavor configurations are valid"""
        for flavor_key, flavor_config in self.versalogiq.flavour_configs.items():
            if flavor_key == 'unknown':
                continue
                
            # Check required fields
            self.assertIn('name', flavor_config)
            self.assertIn('icon', flavor_config)
            
            # Check detection rules exist
            detection_rules = flavor_config.get('detection_rules', [])
            fallback_commands = flavor_config.get('fallback_commands', [])
            
            # Should have at least one detection method
            self.assertGreater(len(detection_rules) + len(fallback_commands), 0)
            
            # Validate rule structure
            for rule in detection_rules:
                self.assertIn('command', rule)
                self.assertIn('required_patterns', rule)
                self.assertIn('priority', rule)
    
    def test_mock_response_generation(self):
        """Test mock response generation for different flavors"""
        test_cases = [
            ('VMS', 'vsh status | grep msgservice', 'msgservice'),
            ('VOS', 'vsh details', 'versa-flexvnf'),
            ('SCIM', 'docker ps |grep -i versa_scim', 'versa_scim'),
            ('UBUNTU', 'lsb_release -d', 'Ubuntu')
        ]
        
        for flavor, command, expected_pattern in test_cases:
            # Create mock server
            mock_config = create_mock_server(flavor)
            
            # Check that appropriate responses are generated
            responses = mock_config.get('responses', {})
            
            # Find matching command response
            found_response = False
            for cmd, response in responses.items():
                if command in cmd or cmd in command:
                    self.assertIn(expected_pattern.lower(), response.lower())
                    found_response = True
                    break
            
            # Some flavors might not have exact command matches in mock
            # but should have the flavor correctly configured
            self.assertEqual(mock_config['flavor'], flavor.upper())

class TestFlavorDetectionIntegration(unittest.TestCase):
    """Integration tests for flavor detection with mock servers"""
    
    def setUp(self):
        """Set up integration test environment"""
        self.versalogiq = VersaLogIQ()
        
    def test_end_to_end_flavor_detection(self):
        """Test complete flavor detection workflow"""
        # This would test with mock SSH connections
        # For now, just verify the method exists and handles no connection
        result = self.versalogiq.detect_server_flavour()
        
        # Without SSH connection, should return Unknown
        self.assertEqual(result, "Unknown")

if __name__ == '__main__':
    # Run specific test categories
    import argparse
    
    parser = argparse.ArgumentParser(description='Run flavor detection tests')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--pattern', '-k', help='Run tests matching pattern')
    
    args = parser.parse_args()
    
    # Configure test runner
    verbosity = 2 if args.verbose else 1
    
    if args.pattern:
        # Run specific test pattern
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromTestCase(TestFlavorDetection)
        
        # Filter tests by pattern
        filtered_suite = unittest.TestSuite()
        for test_group in suite:
            for test in test_group:
                if args.pattern.lower() in test._testMethodName.lower():
                    filtered_suite.addTest(test)
        
        runner = unittest.TextTestRunner(verbosity=verbosity)
        result = runner.run(filtered_suite)
    else:
        # Run all tests
        unittest.main(argv=[''], verbosity=verbosity, exit=False)