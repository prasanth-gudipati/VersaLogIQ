#!/usr/bin/env python3
"""
Mock server responses for VersaLogIQ testing
"""

from typing import Dict, List, Tuple
import time
import re

class MockSSHResponse:
    """Mock SSH response for testing"""
    
    def __init__(self, stdout: str = "", stderr: str = "", delay: float = 0.1):
        self.stdout = stdout
        self.stderr = stderr
        self.delay = delay
        self.executed = False
        
    def execute(self) -> Tuple[str, str]:
        """Simulate command execution with delay"""
        if self.delay > 0:
            time.sleep(self.delay)
        self.executed = True
        return self.stdout, self.stderr

class MockShell:
    """Mock SSH shell for interactive commands"""
    
    def __init__(self, server_config: Dict):
        self.server_config = server_config
        self.responses = server_config.get('responses', {})
        self.sudo_type = server_config.get('sudo_type', 'password_required')
        self.buffer = ""
        self.current_user = server_config.get('username', 'user')
        self.is_root = False
        
    def send(self, command: str):
        """Simulate sending command to shell"""
        command = command.strip()
        
        if command == 'sudo su':
            self._handle_sudo_su()
        elif command in self.responses:
            self.buffer += self.responses[command]
        else:
            # Generic response for unknown commands
            if self.is_root:
                self.buffer += f"root@{self.server_config['hostname']}# "
            else:
                self.buffer += f"{self.current_user}@{self.server_config['hostname']}$ "
    
    def recv_ready(self) -> bool:
        """Simulate checking if data is ready"""
        return len(self.buffer) > 0
    
    def recv(self, size: int) -> bytes:
        """Simulate receiving data from shell"""
        if len(self.buffer) == 0:
            return b""
        
        # Return part of buffer and clear it
        data = self.buffer[:size]
        self.buffer = self.buffer[size:]
        return data.encode('utf-8')
    
    def close(self):
        """Simulate closing shell"""
        self.buffer = ""
    
    def _handle_sudo_su(self):
        """Handle sudo su command based on server configuration"""
        if self.sudo_type == 'passwordless':
            # Direct transition to root
            self.is_root = True
            hostname = self.server_config.get('hostname', 'server')
            self.buffer += f"{self.current_user}@{hostname}: ~] # sudo su\nroot@{hostname}:/home/{self.current_user}# "
        else:
            # Require password
            self.buffer += f"[sudo] password for {self.current_user}: "

class MockSSHClient:
    """Mock SSH client for testing"""
    
    def __init__(self, server_config: Dict):
        self.server_config = server_config
        self.connected = False
        self.shell = None
        
    def set_missing_host_key_policy(self, policy):
        """Mock host key policy setting"""
        pass
    
    def connect(self, hostname: str, username: str, password: str, **kwargs):
        """Mock SSH connection"""
        # Simulate connection delay
        time.sleep(0.1)
        
        # Check if credentials match
        expected_host = self.server_config.get('hostname', 'localhost')
        expected_user = self.server_config.get('username', 'admin')
        expected_pass = self.server_config.get('password', 'password')
        
        if (hostname != expected_host or 
            username != expected_user or 
            password != expected_pass):
            raise Exception(f"Authentication failed for {username}@{hostname}")
        
        self.connected = True
        
    def invoke_shell(self) -> MockShell:
        """Create mock interactive shell"""
        if not self.connected:
            raise Exception("Not connected to server")
        
        self.shell = MockShell(self.server_config)
        return self.shell
    
    def exec_command(self, command: str, timeout: int = 10) -> Tuple[MockSSHResponse, MockSSHResponse, MockSSHResponse]:
        """Execute command and return mock streams"""
        if not self.connected:
            raise Exception("Not connected to server")
        
        # Get response for command
        responses = self.server_config.get('responses', {})
        
        if command in responses:
            stdout_data = responses[command]
            stderr_data = ""
        else:
            # Generic responses for common commands
            if command == 'whoami':
                stdout_data = self.server_config.get('username', 'admin')
                stderr_data = ""
            elif 'find /var/log' in command:
                stdout_data = self._mock_log_file_listing(command)
                stderr_data = ""
            else:
                stdout_data = ""
                stderr_data = f"Command not found: {command}"
        
        # Create mock stream objects
        stdin_mock = MockStreamResponse("")
        stdout_mock = MockStreamResponse(stdout_data)
        stderr_mock = MockStreamResponse(stderr_data)
        
        return stdin_mock, stdout_mock, stderr_mock
    
    def close(self):
        """Close mock connection"""
        self.connected = False
        if self.shell:
            self.shell.close()
    
    def _mock_log_file_listing(self, command: str) -> str:
        """Generate mock log file listing based on command"""
        # Check if .gz files should be excluded
        if '! -name \'*.gz\'' in command:
            log_files = [
                '/var/log/apache2/access.log',
                '/var/log/apache2/error.log',
                '/var/log/auth.log',
                '/var/log/syslog',
                '/var/log/nginx/access.log',
                '/var/log/nginx/error.log'
            ]
        else:
            # Include .gz files if not explicitly excluded
            log_files = [
                '/var/log/apache2/access.log',
                '/var/log/apache2/access.log.1.gz',
                '/var/log/apache2/error.log',
                '/var/log/auth.log',
                '/var/log/auth.log.1.gz', 
                '/var/log/syslog',
                '/var/log/syslog.1.gz',
                '/var/log/nginx/access.log',
                '/var/log/nginx/error.log'
            ]
        
        return '\n'.join(sorted(log_files))

class MockStreamResponse:
    """Mock SSH stream response"""
    
    def __init__(self, data: str):
        self.data = data.encode('utf-8') if isinstance(data, str) else data
        
    def read(self) -> bytes:
        """Read all data from stream"""
        return self.data
    
    def readline(self) -> bytes:
        """Read one line from stream"""
        lines = self.data.split(b'\n')
        return lines[0] + b'\n' if lines else b''

# Flavor detection response generators
class FlavorResponseGenerator:
    """Generate responses for flavor detection commands"""
    
    @staticmethod
    def generate_vms_response(command: str) -> str:
        """Generate VMS-specific responses"""
        if 'vsh status' in command and 'msgservice' in command:
            return "msgservice: running (pid: 1234)"
        return ""
    
    @staticmethod  
    def generate_vos_response(command: str) -> str:
        """Generate VOS-specific responses"""
        if 'vsh details' in command:
            return "versa-flexvnf version 20.2.3"
        elif 'versa-release' in command:
            return "Versa FlexVNF Release 20.2.3"
        return ""
    
    @staticmethod
    def generate_scim_response(command: str) -> str:
        """Generate SCIM-specific responses"""
        if 'docker ps' in command and 'versa_scim' in command:
            return "abcd1234    versa_scim:latest"
        return ""
    
    @staticmethod
    def generate_ecp_response(command: str) -> str:
        """Generate ECP-specific responses"""
        if 'vsh system details' in command and 'concerto' in command:
            return "concerto-platform version 21.1.2"
        return ""
    
    @staticmethod
    def generate_van_response(command: str) -> str:
        """Generate VAN-specific responses"""
        if 'vsh details' in command and 'versa-analytics' in command:
            return "versa-analytics service running"
        return ""
    
    @staticmethod
    def generate_ubuntu_response(command: str) -> str:
        """Generate Ubuntu-specific responses"""
        if 'lsb_release -d' in command:
            return "Description:\tUbuntu 18.04.6 LTS"
        elif '/etc/os-release' in command:
            return 'NAME="Ubuntu"\nVERSION="18.04.6 LTS (Bionic Beaver)"'
        return ""

def create_mock_server(flavor: str, sudo_type: str = 'password_required') -> Dict:
    """Create mock server configuration for specific flavor"""
    base_config = {
        'hostname': f'test-{flavor.lower()}.local',
        'username': 'admin' if flavor != 'SCIM' else 'versa',
        'password': 'test123',
        'flavor': flavor.upper(),
        'sudo_type': sudo_type,
        'responses': {}
    }
    
    # Add flavor-specific responses
    generator_map = {
        'VMS': FlavorResponseGenerator.generate_vms_response,
        'VOS': FlavorResponseGenerator.generate_vos_response,
        'SCIM': FlavorResponseGenerator.generate_scim_response,
        'ECP': FlavorResponseGenerator.generate_ecp_response,
        'VAN': FlavorResponseGenerator.generate_van_response,
        'UBUNTU': FlavorResponseGenerator.generate_ubuntu_response
    }
    
    if flavor.upper() in generator_map:
        generator = generator_map[flavor.upper()]
        # Add common detection commands for this flavor
        common_commands = [
            'vsh status | grep msgservice',
            'vsh details',
            'cat /etc/versa-release', 
            'vsh system details | grep concerto',
            'docker ps |grep -i versa_scim',
            'lsb_release -d',
            'cat /etc/os-release'
        ]
        
        for cmd in common_commands:
            response = generator(cmd)
            if response:
                base_config['responses'][cmd] = response
    
    return base_config

if __name__ == "__main__":
    # Test mock response generation
    print("🧪 Testing Mock Response Generation")
    print("=" * 40)
    
    flavors = ['VMS', 'VOS', 'SCIM', 'ECP', 'VAN', 'UBUNTU']
    
    for flavor in flavors:
        print(f"\n{flavor} Mock Server:")
        mock_config = create_mock_server(flavor)
        print(f"  Hostname: {mock_config['hostname']}")
        print(f"  Username: {mock_config['username']}")
        print(f"  Sudo Type: {mock_config['sudo_type']}")
        print(f"  Responses: {len(mock_config['responses'])} commands")
        
        for cmd, response in mock_config['responses'].items():
            print(f"    {cmd[:30]}... -> {response[:50]}...")
    
    print(f"\n✅ Mock response generation test complete!")