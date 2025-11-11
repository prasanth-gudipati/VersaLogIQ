#!/usr/bin/env python3
"""
Unit tests for SSH connection functionality including sudo handling
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add parent directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from test_config import SUDO_RESPONSE_PATTERNS, TEST_CREDENTIALS
from mock.mock_responses import MockSSHClient, MockShell
from versalogiq_app import VersaLogIQ

class TestSSHConnection(unittest.TestCase):
    """Test cases for SSH connection functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.versalogiq = VersaLogIQ()
        
        # Capture log output
        self.log_messages = []
        self.original_log_output = self.versalogiq.log_output
        self.versalogiq.log_output = self._capture_log_output
    
    def tearDown(self):
        """Clean up after tests"""
        self.versalogiq.log_output = self.original_log_output
        
        # Close any SSH connections
        if self.versalogiq.ssh_client:
            try:
                self.versalogiq.ssh_client.close()
            except:
                pass
    
    def _capture_log_output(self, message, tag):
        """Capture log messages for testing"""
        self.log_messages.append((message, tag))
    
    @patch('paramiko.SSHClient')
    def test_successful_ssh_connection(self, mock_ssh_class):
        """Test successful SSH connection establishment"""
        # Mock SSH client
        mock_client = Mock()
        mock_ssh_class.return_value = mock_client
        mock_client.connect.return_value = None
        
        # Test connection
        result = self.versalogiq.connect_to_server(
            host="test.example.com",
            username="testuser",
            password="testpass",
            key_filename=None
        )
        
        # Verify connection was established
        self.assertTrue(result)
        self.assertTrue(self.versalogiq.connected)
        
        # Verify SSH client was configured correctly
        mock_client.set_missing_host_key_policy.assert_called_once()
        mock_client.connect.assert_called_once()
    
    @patch('paramiko.SSHClient')
    def test_ssh_connection_with_key(self, mock_ssh_class):
        """Test SSH connection using private key"""
        # Mock SSH client
        mock_client = Mock()
        mock_ssh_class.return_value = mock_client
        mock_client.connect.return_value = None
        
        # Test connection with key
        result = self.versalogiq.connect_to_server(
            host="test.example.com",
            username="testuser",
            password=None,
            key_filename="/path/to/key.pem"
        )
        
        # Verify connection was established
        self.assertTrue(result)
        
        # Check that connect was called with key_filename
        call_args = mock_client.connect.call_args
        self.assertIn('key_filename', call_args[1])
        self.assertEqual(call_args[1]['key_filename'], "/path/to/key.pem")
    
    @patch('paramiko.SSHClient')
    def test_ssh_connection_failure(self, mock_ssh_class):
        """Test SSH connection failure handling"""
        # Mock SSH client that fails to connect
        mock_client = Mock()
        mock_ssh_class.return_value = mock_client
        mock_client.connect.side_effect = Exception("Connection failed")
        
        # Test connection
        result = self.versalogiq.connect_to_server(
            host="invalid.host.com",
            username="testuser",
            password="testpass",
            key_filename=None
        )
        
        # Verify connection failed
        self.assertFalse(result)
        self.assertFalse(self.versalogiq.connected)
        
        # Check error in logs
        log_messages_text = [msg[0] for msg in self.log_messages]
        self.assertTrue(any("Connection failed" in msg for msg in log_messages_text))
    
    def test_sudo_pattern_detection_password_required(self):
        """Test sudo detection for password-required responses"""
        # Test various password prompts
        test_patterns = [
            "[sudo] password for testuser:",
            "Password:",
            "testuser@server's password:",
            "sudo password:"
        ]
        
        for pattern in test_patterns:
            needs_password, needs_sudo = self.versalogiq.check_sudo_requirements(pattern)
            self.assertTrue(needs_password, f"Failed to detect password requirement in: {pattern}")
            self.assertTrue(needs_sudo, f"Failed to detect sudo requirement in: {pattern}")
    
    def test_sudo_pattern_detection_passwordless(self):
        """Test sudo detection for passwordless responses"""
        test_patterns = [
            "uid=0(root) gid=0(root)",  # whoami output as root
            "root",  # simple whoami response
            "total 64",  # ls -la output
            "drwxr-xr-x 10 root root 4096 Oct 20 10:30 .",  # directory listing
        ]
        
        for pattern in test_patterns:
            needs_password, needs_sudo = self.versalogiq.check_sudo_requirements(pattern)
            self.assertFalse(needs_password, f"Incorrectly detected password requirement in: {pattern}")
            self.assertFalse(needs_sudo, f"Incorrectly detected sudo requirement in: {pattern}")
    
    def test_sudo_pattern_detection_command_not_found(self):
        """Test sudo detection for command not found scenarios"""
        test_patterns = [
            "sudo: command not found",
            "bash: sudo: command not found",
            "-bash: sudo: command not found"
        ]
        
        for pattern in test_patterns:
            needs_password, needs_sudo = self.versalogiq.check_sudo_requirements(pattern)
            self.assertFalse(needs_password, f"Incorrectly detected password requirement in: {pattern}")
            self.assertFalse(needs_sudo, f"Incorrectly detected sudo requirement in: {pattern}")
    
    @patch('versalogiq_app.VersaLogIQ.execute_ssh_command')
    def test_sudo_handling_password_required(self, mock_execute):
        """Test sudo handling when password is required"""
        # Mock SSH client
        self.versalogiq.ssh_client = Mock()
        self.versalogiq.connected = True
        
        # Mock responses for sudo detection sequence
        def mock_command_execution(command, timeout, use_sudo):
            if command == "whoami":
                return ("testuser", "")
            elif "sudo whoami" in command:
                return ("[sudo] password for testuser:", "")
            return ("", "")
        
        mock_execute.side_effect = mock_command_execution
        
        # Test sudo detection
        sudo_info = self.versalogiq.test_sudo_access()
        
        # Verify sudo was detected as password-required
        self.assertEqual(sudo_info['sudo_available'], True)
        self.assertEqual(sudo_info['requires_password'], True)
        
        # Check log messages
        log_messages_text = [msg[0] for msg in self.log_messages]
        self.assertTrue(any("Sudo requires password" in msg for msg in log_messages_text))
    
    @patch('versalogiq_app.VersaLogIQ.execute_ssh_command')
    def test_sudo_handling_passwordless(self, mock_execute):
        """Test sudo handling for passwordless sudo"""
        # Mock SSH client
        self.versalogiq.ssh_client = Mock()
        self.versalogiq.connected = True
        
        # Mock responses for passwordless sudo
        def mock_command_execution(command, timeout, use_sudo):
            if command == "whoami":
                return ("testuser", "")
            elif "sudo whoami" in command:
                return ("root", "")
            return ("", "")
        
        mock_execute.side_effect = mock_command_execution
        
        # Test sudo detection
        sudo_info = self.versalogiq.test_sudo_access()
        
        # Verify passwordless sudo was detected
        self.assertEqual(sudo_info['sudo_available'], True)
        self.assertEqual(sudo_info['requires_password'], False)
        
        # Check log messages
        log_messages_text = [msg[0] for msg in self.log_messages]
        self.assertTrue(any("Sudo available without password" in msg for msg in log_messages_text))

class TestSSHCommandExecution(unittest.TestCase):
    """Test cases for SSH command execution"""
    
    def setUp(self):
        """Set up test environment"""
        self.versalogiq = VersaLogIQ()
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
    
    def test_execute_ssh_command_success(self):
        """Test successful SSH command execution"""
        # Mock successful command execution
        mock_stdin = Mock()
        mock_stdout = Mock()
        mock_stderr = Mock()
        
        mock_stdout.read.return_value = b"command output"
        mock_stderr.read.return_value = b""
        mock_stdout.channel.recv_exit_status.return_value = 0
        
        self.versalogiq.ssh_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)
        
        # Execute command
        stdout, stderr = self.versalogiq.execute_ssh_command("ls -la", timeout=10)
        
        # Verify results
        self.assertEqual(stdout, "command output")
        self.assertEqual(stderr, "")
        
        # Verify SSH client was called correctly
        self.versalogiq.ssh_client.exec_command.assert_called_once_with("ls -la", timeout=10)
    
    def test_execute_ssh_command_with_sudo(self):
        """Test SSH command execution with sudo"""
        # Mock sudo command execution
        mock_stdin = Mock()
        mock_stdout = Mock()
        mock_stderr = Mock()
        
        mock_stdout.read.return_value = b"root output"
        mock_stderr.read.return_value = b""
        mock_stdout.channel.recv_exit_status.return_value = 0
        
        self.versalogiq.ssh_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)
        
        # Set sudo info
        self.versalogiq.sudo_info = {'sudo_available': True, 'requires_password': False}
        
        # Execute command with sudo
        stdout, stderr = self.versalogiq.execute_ssh_command("cat /var/log/messages", use_sudo=True)
        
        # Verify sudo was used in command
        call_args = self.versalogiq.ssh_client.exec_command.call_args[0][0]
        self.assertTrue(call_args.startswith("sudo "))
    
    def test_execute_ssh_command_timeout(self):
        """Test SSH command execution timeout handling"""
        # Mock timeout scenario
        self.versalogiq.ssh_client.exec_command.side_effect = Exception("Timeout")
        
        # Execute command
        stdout, stderr = self.versalogiq.execute_ssh_command("sleep 100", timeout=5)
        
        # Verify timeout was handled
        self.assertEqual(stdout, "")
        self.assertTrue("timeout" in stderr.lower() or "error" in stderr.lower())
    
    def test_execute_ssh_command_error(self):
        """Test SSH command execution error handling"""
        # Mock error scenario
        mock_stdin = Mock()
        mock_stdout = Mock()
        mock_stderr = Mock()
        
        mock_stdout.read.return_value = b""
        mock_stderr.read.return_value = b"command error"
        mock_stdout.channel.recv_exit_status.return_value = 1
        
        self.versalogiq.ssh_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)
        
        # Execute command
        stdout, stderr = self.versalogiq.execute_ssh_command("invalid_command")
        
        # Verify error was captured
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "command error")
    
    def test_execute_ssh_command_no_connection(self):
        """Test SSH command execution without connection"""
        # Reset connection
        self.versalogiq.ssh_client = None
        self.versalogiq.connected = False
        
        # Execute command
        stdout, stderr = self.versalogiq.execute_ssh_command("ls -la")
        
        # Verify no execution occurred
        self.assertEqual(stdout, "")
        self.assertTrue("not connected" in stderr.lower())

class TestMockSSHIntegration(unittest.TestCase):
    """Test integration with mock SSH responses"""
    
    def setUp(self):
        """Set up mock integration test environment"""
        self.mock_client = MockSSHClient()
    
    def test_mock_ssh_basic_commands(self):
        """Test basic commands with mock SSH client"""
        # Test basic command
        stdin, stdout, stderr = self.mock_client.exec_command("whoami")
        
        result = stdout.read().decode('utf-8')
        self.assertIn("testuser", result)
    
    def test_mock_ssh_sudo_commands(self):
        """Test sudo commands with mock SSH client"""
        # Test sudo command
        stdin, stdout, stderr = self.mock_client.exec_command("sudo whoami")
        
        result = stdout.read().decode('utf-8')
        # Should return password prompt or root depending on mock configuration
        self.assertTrue(len(result) > 0)
    
    def test_mock_ssh_flavor_detection_commands(self):
        """Test flavor detection commands with mock SSH client"""
        test_commands = [
            "vsh status",
            "docker ps",
            "lsb_release -d",
            "cat /etc/os-release"
        ]
        
        for command in test_commands:
            stdin, stdout, stderr = self.mock_client.exec_command(command)
            result = stdout.read().decode('utf-8')
            
            # Should get some response (not empty)
            self.assertIsNotNone(result)

if __name__ == '__main__':
    # Run SSH connection tests
    import argparse
    
    parser = argparse.ArgumentParser(description='Run SSH connection tests')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--category', choices=['connection', 'command', 'mock'], 
                       help='Test category to run')
    
    args = parser.parse_args()
    
    verbosity = 2 if args.verbose else 1
    
    if args.category == 'connection':
        suite = unittest.TestLoader().loadTestsFromTestCase(TestSSHConnection)
    elif args.category == 'command':
        suite = unittest.TestLoader().loadTestsFromTestCase(TestSSHCommandExecution)
    elif args.category == 'mock':
        suite = unittest.TestLoader().loadTestsFromTestCase(TestMockSSHIntegration)
    else:
        # Run all tests
        loader = unittest.TestLoader()
        suite = unittest.TestSuite()
        suite.addTests(loader.loadTestsFromTestCase(TestSSHConnection))
        suite.addTests(loader.loadTestsFromTestCase(TestSSHCommandExecution))
        suite.addTests(loader.loadTestsFromTestCase(TestMockSSHIntegration))
    
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)