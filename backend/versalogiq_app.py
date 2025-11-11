#!/usr/bin/env python3
"""
VersaLogIQ - Docker-based Microservices Application
A comprehensive web-based application for connecting to servers and processing 
log files with real-time command execution display.

Features:
- Web interface for server connection with pre-configured default values
- SSH connection management with automatic sudo elevation
- Real-time command execution display via WebSocket
- Log file scanning and processing capabilities
- Docker-based microservices architecture
- Automatic UI reset on disconnect for clean user experience

UI Components:
- Connection panel with server credentials
- Operations panel with log processing commands  
- Real-time output panel with command execution logs
- System log scanning and display functionality

Technical Details:
- Flask-SocketIO for real-time communication
- Paramiko for SSH connections
- Docker containerized deployment
- Threaded command execution to prevent UI blocking
- ANSI escape code cleaning for clean output display
- Automatic UI state management and reset functionality
"""

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import threading
import queue
import time
import paramiko
import json
import re
from datetime import datetime
import os
import redis
from typing import Dict, List, Tuple

app = Flask(__name__)
app.config['SECRET_KEY'] = 'versalogiq-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*")

class VersaLogIQ:
    def __init__(self, session_id=None):
        # SSH connection variables
        self.ssh_client = None
        self.shell = None
        self.connected = False
        
        # Session tracking
        self.session_id = session_id
        
        # Connection details
        self.host = ""
        self.username = ""
        self.ssh_password = ""
        self.admin_password = ""
        
        # Server flavor detection
        self.detected_flavor = "Unknown"
        self.flavour_configs = {}
        
        # Queue for thread communication
        self.output_queue = queue.Queue()
        
        # Create Logs directory if it doesn't exist
        self.logs_dir = "logs"
        self._ensure_logs_directory()
        
        # Setup persistent log file
        self.persistent_log_file = os.path.join(self.logs_dir, "versalogiq.log")
        
        # Initialize log file if it doesn't exist
        self._initialize_log_file()
        
        # Load flavor configurations
        self._load_flavour_configs()
    
    def _ensure_logs_directory(self):
        """Create Logs directory if it doesn't exist"""
        try:
            if not os.path.exists(self.logs_dir):
                os.makedirs(self.logs_dir)
                print(f"Created logs directory: {self.logs_dir}")
            else:
                print(f"Logs directory already exists: {self.logs_dir}")
        except Exception as e:
            print(f"Warning: Could not create logs directory: {str(e)}")
            # Fall back to current directory
            self.logs_dir = "."
    
    def log_output(self, message, tag="normal"):
        """Add message to output display with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Emit to web interface - use instance session_id if available
        if self.session_id:
            socketio.emit('log_output', {
                'message': message,
                'tag': tag,
                'timestamp': timestamp
            }, room=self.session_id)
        else:
            # Fallback: emit to all clients (for backward compatibility)
            socketio.emit('log_output', {
                'message': message,
                'tag': tag,
                'timestamp': timestamp
            })
        
        # Also write to persistent log file
        self._write_to_log_file(message, tag)
    
    def _write_to_log_file(self, message, tag="normal"):
        """Write message to persistent log file with timestamp and decorative separator"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Create log entry with decorative separator for new sessions/operations
            if tag == "session_start":
                log_entry = f"\n{'='*80}\n🚀 NEW SESSION STARTED - {timestamp}\n{'='*80}\n{message}\n"
            elif tag == "operation_start":
                log_entry = f"\n{'-'*60}\n⚡ NEW OPERATION - {timestamp}\n{'-'*60}\n{message}\n"
            else:
                log_entry = f"[{timestamp}] [{tag.upper()}] {message}\n"
            
            # Append to the persistent log file
            with open(self.persistent_log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry)
                
        except Exception as e:
            # Don't let logging errors break the application
            print(f"Warning: Could not write to log file: {str(e)}")
    
    def start_new_session_log(self):
        """Start a new session in the log file with decorative separator"""
        self._write_to_log_file(f"VersaLogIQ Session Started", "session_start")
    
    def start_new_operation_log(self, operation_name):
        """Start a new operation in the log file with decorative separator"""
        self._write_to_log_file(f"Starting Operation: {operation_name}", "operation_start")
    
    def _initialize_log_file(self):
        """Initialize the log file with a header if it doesn't exist or is empty"""
        try:
            # Check if log file exists and has content
            needs_header = True
            if os.path.exists(self.persistent_log_file):
                with open(self.persistent_log_file, 'r') as f:
                    content = f.read().strip()
                    if content:
                        needs_header = False
            
            if needs_header:
                header = f"""{'='*100}
🔧 VERSALOGIQ - PERSISTENT LOG FILE
{'='*100}
Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Purpose: This file contains all VersaLogIQ activities in chronological order
Note: Each new session and operation is marked with decorative separators
{'='*100}

"""
                with open(self.persistent_log_file, 'w', encoding='utf-8') as f:
                    f.write(header)
                    
        except Exception as e:
            print(f"Warning: Could not initialize log file: {str(e)}")
    
    def _load_flavour_configs(self) -> bool:
        """Load server flavour detection configurations"""
        flavour_config_file = "config/server_flavors.json"
        try:
            if not os.path.exists(flavour_config_file):
                print(f"⚠️  Flavour config file not found: {flavour_config_file}")
                print("📝 Flavour detection will be skipped")
                return False
                
            with open(flavour_config_file, 'r') as f:
                flavour_data = json.load(f)
                
            self.flavour_configs = flavour_data.get('server_flavors', {})
            print(f"✅ Loaded {len(self.flavour_configs)} flavour detection configurations")
            return True
            
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON format in flavour config: {str(e)}")
            return False
        except Exception as e:
            print(f"❌ Error loading flavour config: {str(e)}")
            return False
    
    def execute_ssh_command(self, command: str, timeout: int = 15, use_sudo: bool = False) -> Tuple[str, str]:
        """Execute a command via SSH and return stdout, stderr"""
        if not self.ssh_client:
            return "", "No SSH connection available"
            
        try:
            original_command = command
            if use_sudo:
                # Check if this is a VMS-specific command that needs root shell
                if command.strip().startswith('vsh status') and 'msgservice' in command:
                    self.log_output(f"🔐 Executing VMS command with sudo shell: {command}", "info")
                    return self._execute_with_sudo_shell(command, timeout)
                else:
                    self.log_output(f"🔐 Executing with sudo prefix: {command}", "info")
                    return self._execute_with_sudo_prefix(command, timeout)
            else:
                self.log_output(f"🔓 Executing without sudo: {command}", "info")
            
            # Add a small delay to allow shell to stabilize
            time.sleep(0.5)
            
            # For VOS commands (vsh), try to source the environment first
            if original_command.strip().startswith('vsh'):
                # Try multiple approaches for VOS commands
                vos_commands = [
                    command,  # Try as specified
                    f"source /etc/profile && {command}",  # Try with profile
                    f"export PATH=/opt/versa/bin:$PATH && {command}",  # Try with VOS path
                    f"/opt/versa/bin/{original_command}"  # Try with full path
                ]
                
                for vos_cmd in vos_commands:
                    stdin, stdout, stderr = self.ssh_client.exec_command(vos_cmd, timeout=timeout)
                    time.sleep(1.0)
                    
                    stdout_data = stdout.read().decode('utf-8', errors='ignore').strip()
                    stderr_data = stderr.read().decode('utf-8', errors='ignore').strip()
                    
                    # If we got output or no "command not found" error, use this result
                    if stdout_data or ("command not found" not in stderr_data and "No such file" not in stderr_data):
                        return stdout_data, stderr_data
                
                # If all VOS commands failed, return the last result
                return stdout_data, stderr_data
            else:
                stdin, stdout, stderr = self.ssh_client.exec_command(command, timeout=timeout)
                time.sleep(1.0)
                
                stdout_data = stdout.read().decode('utf-8', errors='ignore').strip()
                stderr_data = stderr.read().decode('utf-8', errors='ignore').strip()
                
                return stdout_data, stderr_data
            
        except Exception as e:
            return "", str(e)
    
    def _execute_with_sudo_shell(self, command: str, timeout: int = 15) -> Tuple[str, str]:
        """Execute a command using interactive shell with sudo su (similar to versalogiq_app.py)"""
        try:
            # Create interactive shell
            shell = self.ssh_client.invoke_shell()
            time.sleep(1)
            shell.recv(10000)  # Clear banner
            
            # Execute sudo su
            shell.send("sudo su\n")
            
            # Wait for password prompt
            buff = ""
            start_time = time.time()
            while time.time() - start_time < 10:  # 10 second timeout
                if shell.recv_ready():
                    resp = shell.recv(1000).decode('utf-8', errors='ignore')
                    buff += resp
                    if "password for" in buff.lower():
                        break
                time.sleep(0.2)
            
            if "password for" not in buff.lower():
                shell.close()
                return "", "Sudo password prompt not found"
            
            # Send password (use admin password)
            shell.send(self.admin_password + "\n")
            time.sleep(1.5)
            
            # Check if sudo was successful
            output = shell.recv(10000).decode('utf-8', errors='ignore')
            
            # Now execute the actual command
            shell.send(f"{command}\n")
            time.sleep(2)
            
            # Collect output
            command_output = ""
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                if shell.recv_ready():
                    chunk = shell.recv(4096).decode('utf-8', errors='ignore')
                    command_output += chunk
                    if chunk.endswith('# ') or chunk.endswith('$ '):
                        break
                time.sleep(0.1)
            
            # Clean up
            shell.send("exit\n")
            time.sleep(0.5)
            shell.close()
            
            # Clean the output - remove ANSI codes and command echoes
            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            cleaned_output = ansi_escape.sub('', command_output)
            
            # Remove command echo and prompts
            lines = cleaned_output.strip().split('\n')
            result_lines = []
            for line in lines:
                line = line.strip()
                # Skip command echo, prompts, and empty lines  
                if (not line or 
                    line.startswith(command) or
                    line.endswith('# ') or 
                    line.endswith('$ ') or
                    line.startswith('[root@')):
                    continue
                result_lines.append(line)
            
            result_output = '\n'.join(result_lines)
            return result_output, ""
            
        except Exception as e:
            return "", f"Sudo shell execution failed: {str(e)}"
    
    def _execute_with_sudo_prefix(self, command: str, timeout: int = 15) -> Tuple[str, str]:
        """Execute a command using sudo prefix with interactive shell (for ECP and similar systems)"""
        try:
            self.log_output(f"🔍 Using interactive shell approach for: {command}", "info")
            
            password = self.admin_password
            
            # Create interactive shell (like the manual test)
            shell = self.ssh_client.invoke_shell()
            time.sleep(1)
            
            # Clear any initial output/banner
            if shell.recv_ready():
                shell.recv(10000)
            
            # Send the command directly (it will prompt for sudo password)
            shell.send(f"{command}\n")
            
            # Wait for sudo password prompt
            output_buffer = ""
            start_time = time.time()
            while time.time() - start_time < 10:  # 10 second timeout
                if shell.recv_ready():
                    chunk = shell.recv(1000).decode('utf-8', errors='ignore')
                    output_buffer += chunk
                    # Check if we got the sudo password prompt
                    if "[sudo] password for" in output_buffer:
                        break
                time.sleep(0.2)
            
            if "[sudo] password for" not in output_buffer:
                shell.close()
                return "", "No sudo password prompt found"
            
            # Send the password
            shell.send(password + "\n")
            time.sleep(3)  # Wait for command to execute
            
            # Collect the output
            final_output = ""
            start_time = time.time()
            while time.time() - start_time < 5:  # 5 second timeout for output
                if shell.recv_ready():
                    chunk = shell.recv(4096).decode('utf-8', errors='ignore')
                    final_output += chunk
                else:
                    break
                time.sleep(0.1)
            
            shell.close()
            
            self.log_output(f"📊 Raw interactive output: '{final_output}'", "info")
            
            # Clean the output - remove ANSI codes, command echoes, and prompts
            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            cleaned_output = ansi_escape.sub('', final_output)
            
            # Split into lines and filter
            lines = cleaned_output.split('\n')
            result_lines = []
            
            for line in lines:
                line = line.strip()
                # Skip empty lines, command echoes, prompts, and sudo messages
                if (not line or 
                    line == command or  # Skip command echo
                    "[sudo] password for" in line or
                    line == password or  # Skip password echo
                    line.endswith('$ ') or
                    line.endswith('# ') or
                    line.startswith('admin@') or  # Skip shell prompts
                    line.startswith('$') or
                    line.startswith('#')):
                    continue
                
                # Keep lines that look like actual output
                if line:
                    result_lines.append(line)
            
            result_output = '\n'.join(result_lines)
            
            self.log_output(f"📋 Final cleaned output: '{result_output}'", "info")
            
            return result_output, ""
            
        except Exception as e:
            self.log_output(f"❌ Interactive shell execution failed: {str(e)}", "error")
            return "", f"Interactive sudo execution failed: {str(e)}"

    def detect_server_flavour(self) -> str:
        """Detect the actual server flavour using detection rules"""
        if not self.flavour_configs:
            self.log_output("⚠️  No flavour configuration available - detection skipped", "info")
            return "Unknown"
        
        self.log_output(f"🔍 Detecting server flavour for {self.host}...", "info")
        
        # Sort flavours by priority (highest first)
        flavour_items = []
        for flavour_key, flavour_config in self.flavour_configs.items():
            if flavour_key == 'unknown':  # Skip unknown as it's the fallback
                continue
                
            detection_rules = flavour_config.get('detection_rules', [])
            fallback_commands = flavour_config.get('fallback_commands', [])
            
            # Add primary detection rules
            for rule in detection_rules:
                rule['flavour_key'] = flavour_key
                rule['flavour_name'] = flavour_config.get('name', flavour_key)
                rule['flavour_icon'] = flavour_config.get('icon', '❓')
                flavour_items.append(rule)
            
            # Add fallback commands
            for rule in fallback_commands:
                rule['flavour_key'] = flavour_key
                rule['flavour_name'] = flavour_config.get('name', flavour_key)
                rule['flavour_icon'] = flavour_config.get('icon', '❓')
                flavour_items.append(rule)
        
        # Sort by priority (highest first)
        flavour_items.sort(key=lambda x: x.get('priority', 0), reverse=True)
        
        # Test each detection rule until we find a match
        for rule in flavour_items:
            try:
                command = rule.get('command', '')
                use_sudo = rule.get('use_sudo', False)
                required_patterns = rule.get('required_patterns', [])
                pattern_match_type = rule.get('pattern_match_type', 'contains')
                case_sensitive = rule.get('case_sensitive', False)
                timeout = rule.get('timeout', 15)
                flavour_name = rule['flavour_name']
                flavour_icon = rule['flavour_icon']
                priority = rule.get('priority', 0)
                
                self.log_output(f"🧪 Testing {flavour_name} (Priority: {priority}) - Command: {command}", "info")
                self.log_output(f"🔧 Use sudo: {use_sudo}", "info")
                
                stdout, stderr = self.execute_ssh_command(command, timeout, use_sudo)
                
                # Debug output for VOS detection
                if 'vsh' in command.lower():
                    self.log_output(f"📝 Command output length: {len(stdout)} chars", "info")
                    if stdout:
                        self.log_output(f"📝 First 200 chars: {stdout[:200]}...", "info")
                    if stderr:
                        self.log_output(f"⚠️  Error output: {stderr[:200]}...", "info")
                
                # Check if all required patterns are found
                if self._check_patterns(stdout, required_patterns, pattern_match_type, case_sensitive):
                    self.log_output(f"✅ Server flavour detected: {flavour_icon} {flavour_name}", "success")
                    return flavour_name
                elif stdout or stderr:
                    self.log_output(f"❌ Pattern not found for {flavour_name}", "info")
                    # Debug output for pattern matching
                    if 'vsh' in command.lower() and required_patterns:
                        self.log_output(f"🔍 Looking for patterns: {required_patterns}", "info")
                        for pattern in required_patterns:
                            search_text = stdout if case_sensitive else stdout.lower()
                            search_pattern = pattern if case_sensitive else pattern.lower()
                            found = search_pattern in search_text
                            self.log_output(f"🔍 Pattern '{pattern}' {'✅ FOUND' if found else '❌ NOT FOUND'}", "info")
                else:
                    self.log_output(f"⚠️  No output from command for {flavour_name}", "info")
                    
            except Exception as e:
                self.log_output(f"❌ Error testing {rule.get('flavour_name', 'unknown')}: {str(e)}", "error")
                continue
        
        self.log_output(f"❓ No flavour detected, defaulting to Unknown", "info")
        return "Unknown"
    
    def _check_patterns(self, text: str, patterns: List[str], match_type: str = 'contains', case_sensitive: bool = False) -> bool:
        """Check if all required patterns are found in the text"""
        if not patterns:
            return False
            
        search_text = text if case_sensitive else text.lower()
        
        for pattern in patterns:
            search_pattern = pattern if case_sensitive else pattern.lower()
            
            if match_type == 'contains':
                if search_pattern not in search_text:
                    return False
            elif match_type == 'regex':
                flags = 0 if case_sensitive else re.IGNORECASE
                if not re.search(search_pattern, text, flags):
                    return False
            elif match_type == 'exact':
                if search_pattern != search_text:
                    return False
        
        return True
    
    def _analyze_connection_error(self, error, host, username):
        """Analyze connection error and provide user-friendly error details"""
        error_str = str(error).lower()
        error_type = type(error).__name__
        
        # DNS Resolution errors
        if "name or service not known" in error_str or "nodename nor servname provided" in error_str:
            return {
                'type': 'DNS_ERROR',
                'title': '🌐 DNS Resolution Failed',
                'simple_message': f'Cannot resolve hostname: {host}',
                'detailed_message': f'The hostname "{host}" could not be resolved to an IP address. Please check:\n• Hostname spelling\n• Network connectivity\n• DNS server configuration',
                'suggestions': [
                    f'Verify hostname spelling: {host}',
                    'Check if you can access other websites',
                    'Try using an IP address instead of hostname',
                    'Contact your network administrator'
                ],
                'technical_error': str(error)
            }
        
        # Network unreachable / Connection refused
        elif "connection refused" in error_str or "no route to host" in error_str:
            return {
                'type': 'NETWORK_ERROR',
                'title': '🔌 Network Connection Failed',
                'simple_message': f'Cannot reach server: {host}',
                'detailed_message': f'The server "{host}" is not reachable or refused the connection. Please check:\n• Server is running and accessible\n• Firewall settings\n• Network connectivity',
                'suggestions': [
                    'Verify the server is powered on and running',
                    'Check firewall rules on both client and server',
                    'Ensure SSH service is running on the server',
                    'Test connectivity with ping or telnet'
                ],
                'technical_error': str(error)
            }
        
        # Connection timeout
        elif "timed out" in error_str or "timeout" in error_str:
            return {
                'type': 'TIMEOUT_ERROR',
                'title': '⏱️ Connection Timeout',
                'simple_message': f'Connection to {host} timed out',
                'detailed_message': f'The connection to "{host}" timed out. The server may be slow to respond or unreachable.',
                'suggestions': [
                    'Check if the server is responding slowly',
                    'Verify network connectivity',
                    'Try increasing timeout settings',
                    'Check if server is under heavy load'
                ],
                'technical_error': str(error)
            }
        
        # Authentication errors
        elif "authentication failed" in error_str or "permission denied" in error_str:
            return {
                'type': 'AUTH_ERROR',
                'title': '🔐 Authentication Failed',
                'simple_message': f'Invalid credentials for user: {username}',
                'detailed_message': f'Authentication failed for user "{username}". Please check:\n• Username and password are correct\n• Account is not locked\n• SSH key permissions',
                'suggestions': [
                    'Verify username and password are correct',
                    'Check if account is locked or disabled',
                    'Ensure SSH service allows password authentication',
                    'Contact your system administrator'
                ],
                'technical_error': str(error)
            }
        
        # SSH Protocol errors
        elif "protocol" in error_str or "ssh" in error_str:
            return {
                'type': 'SSH_ERROR',
                'title': '🔧 SSH Protocol Error', 
                'simple_message': f'SSH protocol error connecting to {host}',
                'detailed_message': f'There was an SSH protocol error. This could indicate version incompatibility or configuration issues.',
                'suggestions': [
                    'Verify SSH service is running on the server',
                    'Check SSH configuration on the server',
                    'Ensure compatible SSH protocol versions',
                    'Review SSH logs on the server'
                ],
                'technical_error': str(error)
            }
        
        # Generic/Unknown errors
        else:
            return {
                'type': 'UNKNOWN_ERROR',
                'title': '❌ Connection Error',
                'simple_message': f'Failed to connect to {host}',
                'detailed_message': f'An unexpected error occurred while connecting to "{host}". Please review the technical details below.',
                'suggestions': [
                    'Check all connection parameters',
                    'Verify server accessibility',
                    'Review the technical error message',
                    'Contact technical support if needed'
                ],
                'technical_error': str(error)
            }
    
    def connect_to_server(self, host, username, ssh_password, admin_password=None):
        """Connect to the SSH server in a separate thread"""
        self.host = host
        self.username = username
        self.ssh_password = ssh_password
        # Automatically assign admin password same as SSH password if not provided
        self.admin_password = admin_password if admin_password else ssh_password
        
        # Start new session in log file
        self.start_new_session_log()
        
        try:
            self.log_output("Attempting SSH connection...", "info")
            
            # Create SSH client
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Connect
            self.ssh_client.connect(
                hostname=host,
                username=username,
                password=ssh_password,
                look_for_keys=False,
                timeout=10
            )
            
            self.log_output(f"SSH connection successful to {host}", "success")
            
            # Create shell
            self.shell = self.ssh_client.invoke_shell()
            time.sleep(1)
            self.shell.recv(10000)  # Clear banner
            
            self.log_output("Shell session established", "success")
            
            # Execute sudo su
            self.log_output("Executing 'sudo su' command...", "command")
            self.shell.send("sudo su\n")
            
            # Wait for password prompt OR immediate root shell
            buff = ""
            start_time = time.time()
            password_required = False
            
            self.log_output("Waiting for sudo response...", "info")
            
            while time.time() - start_time < 10:  # 10 second timeout
                if self.shell.recv_ready():
                    resp = self.shell.recv(1000).decode('utf-8', errors='ignore')
                    buff += resp
                    self.log_output(f"Debug - Received chunk: '{resp.strip()}'", "info")
                    
                    # Check for password prompt (multiple variations)
                    if ("password for" in buff.lower() or 
                        "password:" in buff.lower() or
                        "[sudo] password" in buff.lower()):
                        password_required = True
                        self.log_output("Password prompt detected", "info")
                        break
                    
                    # Check for immediate root shell (passwordless sudo)
                    if ("root@" in buff or 
                        buff.strip().endswith("# ") or
                        "# " in buff):
                        self.log_output("Passwordless sudo detected - no password required", "success")
                        break
                        
                time.sleep(0.2)
            
            # Handle password requirement
            if password_required:
                self.log_output("Sudo password required - sending password", "info")
                # Send admin password
                self.shell.send(admin_password + "\n")
                time.sleep(1.5)
                
                # Check if sudo was successful
                output = self.shell.recv(10000).decode('utf-8', errors='ignore')
                self.log_output("Sudo elevation successful (with password)", "success")
            elif ("root@" in buff or 
                  buff.strip().endswith("# ") or
                  "# " in buff):
                self.log_output("Sudo elevation successful (passwordless)", "success")
            else:
                # Log the actual buffer content for debugging
                self.log_output(f"Debug - Final buffer: '{buff.strip()}'", "info")
                self.log_output(f"Debug - Buffer length: {len(buff)}", "info")
                self.log_output(f"Debug - Looking for: 'password for' or 'root@' or '# '", "info")
                raise Exception("Sudo command failed - neither password prompt nor root shell detected")
            
            # Update connection state
            self.connected = True
            if self.session_id:
                socketio.emit('connection_status', {'connected': True, 'message': 'Connected successfully'}, room=self.session_id)
            else:
                socketio.emit('connection_status', {'connected': True, 'message': 'Connected successfully'})
            
            # Detect server flavor after successful connection
            self.log_output("", "normal")  # Empty line for separation
            self.log_output("=" * 60, "info")
            self.log_output("🔍 STARTING SERVER FLAVOR DETECTION", "info")
            self.log_output("=" * 60, "info")
            self.detected_flavor = self.detect_server_flavour()
            self.log_output("=" * 60, "success")
            self.log_output("✅ FLAVOR DETECTION COMPLETED", "success")
            self.log_output("=" * 60, "success")
            self.log_output("", "normal")  # Empty line for separation
            
            # Send flavor information to the frontend
            if self.session_id:
                socketio.emit('flavor_detected', {'flavor': self.detected_flavor}, room=self.session_id)
                # Signal that flavor detection is complete and operations section should be shown
                socketio.emit('flavor_detection_complete', {}, room=self.session_id)
            else:
                socketio.emit('flavor_detected', {'flavor': self.detected_flavor})
                # Signal that flavor detection is complete and operations section should be shown
                socketio.emit('flavor_detection_complete', {})
            
            # Automatically start log scanning after flavor detection
            self.log_output("Connection successful! Starting log file scanning...", "success")
            time.sleep(1)
            self.scan_system_logs()
            
        except Exception as e:
            # Analyze the error and provide user-friendly feedback
            error_details = self._analyze_connection_error(e, host, username)
            
            self.log_output(f"Connection failed: {str(e)}", "error")
            self.connected = False
            
            if self.session_id:
                socketio.emit('connection_status', {
                    'connected': False, 
                    'message': error_details['simple_message'],
                    'error_details': error_details
                }, room=self.session_id)
            else:
                socketio.emit('connection_status', {
                    'connected': False, 
                    'message': error_details['simple_message'],
                    'error_details': error_details
                })
    
    def disconnect_from_server(self):
        """Disconnect from SSH server"""
        if not self.connected:
            return
        
        try:
            self.log_output("Disconnecting from server...", "info")
            if self.shell:
                self.shell.send("exit\n")
                time.sleep(0.5)
            if self.ssh_client:
                self.ssh_client.close()
        except Exception as e:
            self.log_output(f"Error during disconnect: {str(e)}", "error")
        
        # Log session end
        self._write_to_log_file(f"SESSION ENDED - Disconnected from {self.host}", "session_start")
        
        # Reset connection state
        self.connected = False
        self.ssh_client = None
        self.shell = None
        self.detected_flavor = "Unknown"
        
        self.log_output("Disconnected from server", "info")
        if self.session_id:
            socketio.emit('connection_status', {'connected': False, 'message': 'Disconnected'}, room=self.session_id)
        else:
            socketio.emit('connection_status', {'connected': False, 'message': 'Disconnected'})
    
    def scan_system_logs(self):
        """Scan for all log files in /var/log directory and subdirectories"""
        if not self.connected:
            self.log_output("Error: Not connected to server", "error")
            return {}
        
        # Start new operation log
        self.start_new_operation_log("System Log Files Scanning")
        
        try:
            self.log_output("Scanning for log files in /var/log directory (excluding .gz files)", "info")
            
            # Execute find command to get all log files, excluding .gz files
            command = "find /var/log -type f -name '*.log*' ! -name '*.gz' ! -name '*.gz.*' | sort"
            self.log_output(f"Executing command: {command}", "command")
            self.shell.send(f"{command}\n")
            time.sleep(3)
            
            # Collect output
            output = self._collect_command_output(timeout=15)
            cleaned_output = self._clean_ansi_codes(output)
            lines = cleaned_output.strip().split('\n')
            
            log_files = {}
            
            # Process log files
            for line in lines:
                line = line.strip()
                # Skip command echo, prompts, and empty lines
                if (not line or 
                    line.startswith('find') or 
                    line.endswith('# ') or 
                    line.endswith('$ ') or
                    line.startswith('[root@')):
                    continue
                
                # Check if it's a valid log file path and exclude .gz files (double-check)
                if (line.startswith('/var/log/') and 
                    ('log' in line.lower()) and 
                    not line.endswith('.gz') and
                    '.gz.' not in line.lower()):
                    # Extract directory and filename
                    path_parts = line.split('/')
                    if len(path_parts) >= 3:  # /var/log/[directory]/[filename] or /var/log/[filename]
                        if len(path_parts) == 3:  # Direct file in /var/log
                            directory = 'var-log-root'
                        else:
                            directory = path_parts[3] if len(path_parts) > 3 else 'var-log-root'
                        filename = path_parts[-1]
                        
                        # Additional check: skip any filename containing .gz
                        if '.gz' in filename.lower():
                            continue
                        
                        if directory not in log_files:
                            log_files[directory] = []
                        
                        log_files[directory].append({
                            'name': filename,
                            'path': line,
                            'directory': directory
                        })
            
            # Sort files within each directory
            for directory in log_files:
                log_files[directory].sort(key=lambda x: x['name'])
            
            total_files = sum(len(files) for files in log_files.values())
            total_dirs = len(log_files)
            self.log_output(f"-> Found {total_files} log files across {total_dirs} directories (all .gz files excluded)", "success")
            
            # Log summary for each directory
            for directory, files in log_files.items():
                file_names = [f['name'] for f in files[:3]]  # Show first 3 files
                file_summary = ', '.join(file_names) + ('...' if len(files) > 3 else '')
                self.log_output(f"  {directory}: {len(files)} files -> {file_summary}", "info")
            
            # Send log files data to web interface
            if self.session_id:
                socketio.emit('log_files_response', {'log_files': log_files}, room=self.session_id)
            else:
                socketio.emit('log_files_response', {'log_files': log_files})
            
            return log_files
            
        except Exception as e:
            self.log_output(f"Error scanning log files: {str(e)}", "error")
            return {}
    
    def get_log_file_tail(self, log_file_path, lines=250, log_filter='all'):
        """Get the last N lines of a log file with filtering options"""
        if not self.connected:
            self.log_output("Error: Not connected to server", "error")
            return None
        
        try:
            self.log_output(f"Getting last {lines} lines from: {log_file_path} (filter: {log_filter})", "info")
            
            # Build command based on filter type
            if log_filter == 'all':
                # Show last N lines as raw format
                command = f"tail -n {lines} \"{log_file_path}\""
            elif log_filter == 'errors':
                # Show only ERROR messages in last N lines with 2 spaces before each error
                command = f"tail -n {lines} \"{log_file_path}\" | grep -i error | sed 's/^/  /'"
            elif log_filter == 'pretty':
                # Show all N logs but highlight errors with empty line before each error
                command = f"tail -n {lines} \"{log_file_path}\" | sed '/[Ee][Rr][Rr][Oo][Rr]/i\\\\'"
            else:
                command = f"tail -n {lines} \"{log_file_path}\""
            
            self.log_output(f"Executing command: {command}", "command")
            
            self.shell.send(f"{command}\n")
            time.sleep(2)
            
            # Collect output
            output = self._collect_command_output(timeout=20)
            cleaned_output = self._clean_ansi_codes(output)
            lines_output = cleaned_output.strip().split('\n')
            
            # Clean lines and remove command echo/prompts
            cleaned_lines = []
            for line in lines_output:
                line = line.rstrip()
                # Skip command echo, prompts, and empty continuation
                if (line.startswith('tail ') or 
                    line.endswith('# ') or 
                    line.endswith('$ ') or
                    line.startswith('[root@')):
                    continue
                
                cleaned_lines.append(line)
            
            # Join lines back together
            log_content = '\n'.join(cleaned_lines)
            
            self.log_output(f"-> Successfully retrieved {len(cleaned_lines)} lines from log file", "success")
            
            return {
                'path': log_file_path,
                'lines_requested': lines,
                'lines_retrieved': len(cleaned_lines),
                'content': log_content,
                'command': command,
                'filter': log_filter,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.log_output(f"Error getting log file tail: {str(e)}", "error")
            return None
    
    def _collect_command_output(self, timeout=10):
        """Collect output from shell command"""
        output = ""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.shell.recv_ready():
                chunk = self.shell.recv(4096).decode('utf-8', errors='ignore')
                output += chunk
                if chunk.endswith('# ') or chunk.endswith('$ '):
                    break
            time.sleep(0.1)
        
        return output
    
    def _clean_ansi_codes(self, text):
        """Remove ANSI escape codes from text"""
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)

# Session-based instances - each client gets their own instance
client_instances = {}

def get_client_instance():
    """Get or create a VersaLogIQ instance for the current client session"""
    from flask import has_request_context
    
    if has_request_context() and hasattr(request, 'sid'):
        session_id = request.sid
    else:
        session_id = 'default'
    
    if session_id not in client_instances:
        print(f"DEBUG: Creating new VersaLogIQ instance for session: {session_id}")
        client_instances[session_id] = VersaLogIQ(session_id=session_id)
    
    return client_instances[session_id]

def cleanup_client_instance(session_id):
    """Clean up client instance when session disconnects"""
    if session_id in client_instances:
        print(f"DEBUG: Cleaning up VersaLogIQ instance for session: {session_id}")
        try:
            client_instances[session_id].disconnect_from_server()
        except:
            pass
        del client_instances[session_id]

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/health')
def health():
    """Health check endpoint for Docker"""
    return jsonify({'status': 'healthy', 'service': 'VersaLogIQ'}), 200

@app.route('/version')
def version():
    """Version endpoint to verify builds"""
    return jsonify({
        'service': 'VersaLogIQ',
        'version': '1.0.1',
        'build_time': datetime.now().isoformat(),
        'features': [
            'SSH Connection Management',
            'Real-time Log Processing', 
            'System Log Scanning',
            'Docker Microservices Architecture',
            'Enhanced Update Process'
        ]
    }), 200

@app.route('/api/test_connection', methods=['POST'])
def api_test_connection():
    """REST API endpoint to test connection to a specific server"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No JSON data provided'}), 400
        
        # Extract connection parameters
        hostname = data.get('hostname')
        username = data.get('username')
        password = data.get('password')
        key_filename = data.get('key_filename')
        expected_flavor = data.get('expected_flavor')
        use_mock = data.get('use_mock', False)
        
        if not hostname or not username:
            return jsonify({
                'success': False, 
                'error': 'hostname and username are required'
            }), 400
        
        if not password and not key_filename:
            return jsonify({
                'success': False,
                'error': 'Either password or key_filename is required'
            }), 400
        
        # Create a temporary VersaLogIQ instance for testing
        test_client = VersaLogIQ()
        
        start_time = time.time()
        
        # Mock response for testing
        if use_mock:
            connection_time = time.time() - start_time + 0.5  # Simulate connection time
            return jsonify({
                'success': True,
                'hostname': hostname,
                'detected_flavor': expected_flavor or 'VMS',
                'sudo_available': True,
                'requires_password': False,
                'connection_time': round(connection_time, 3),
                'mock': True
            })
        
        # Attempt real connection
        success = test_client.connect_to_server(hostname, username, password, key_filename)
        connection_time = time.time() - start_time
        
        if not success:
            return jsonify({
                'success': False,
                'hostname': hostname,
                'error': 'Failed to establish SSH connection',
                'connection_time': round(connection_time, 3)
            })
        
        # Detect server flavor
        detected_flavor = test_client.detect_server_flavour()
        
        # Test sudo access
        sudo_info = test_client.test_sudo_access()
        
        # Close test connection
        test_client.ssh_client.close()
        
        return jsonify({
            'success': True,
            'hostname': hostname,
            'detected_flavor': detected_flavor,
            'sudo_available': sudo_info.get('sudo_available', False),
            'requires_password': sudo_info.get('requires_password', True),
            'connection_time': round(connection_time, 3)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Connection test failed: {str(e)}'
        }), 500

@app.route('/api/check_all_servers', methods=['POST'])
def api_check_all_servers():
    """REST API endpoint to check connectivity to all servers in ssh_hosts.json"""
    try:
        data = request.get_json() or {}
        use_mock = data.get('use_mock', False)
        
        # Load servers from ssh_hosts.json
        ssh_hosts_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'ssh_hosts.json')
        
        try:
            with open(ssh_hosts_file, 'r') as f:
                hosts_data = json.load(f)
                servers = hosts_data.get('hosts', [])
        except FileNotFoundError:
            return jsonify({
                'success': False,
                'error': 'ssh_hosts.json file not found'
            }), 404
        except json.JSONDecodeError:
            return jsonify({
                'success': False,
                'error': 'Invalid JSON in ssh_hosts.json'
            }), 400
        
        if not servers:
            return jsonify({
                'success': False,
                'error': 'No servers configured in ssh_hosts.json'
            }), 400
        
        results = []
        successful = 0
        failed = 0
        
        for server in servers:
            try:
                # Mock response for testing
                if use_mock:
                    result = {
                        'hostname': server['hostname'],
                        'name': server['name'],
                        'success': True,
                        'detected_flavor': server['flavour'],
                        'connection_time': 0.5,
                        'mock': True
                    }
                    successful += 1
                else:
                    # Test real connection
                    test_client = VersaLogIQ()
                    start_time = time.time()
                    
                    success = test_client.connect_to_server(
                        server['hostname'],
                        server['user'],
                        server['password']
                    )
                    
                    connection_time = time.time() - start_time
                    
                    if success:
                        detected_flavor = test_client.detect_server_flavour()
                        sudo_info = test_client.test_sudo_access()
                        test_client.ssh_client.close()
                        
                        result = {
                            'hostname': server['hostname'],
                            'name': server['name'],
                            'success': True,
                            'detected_flavor': detected_flavor,
                            'expected_flavor': server['flavour'],
                            'flavor_match': detected_flavor == server['flavour'],
                            'sudo_available': sudo_info.get('sudo_available', False),
                            'connection_time': round(connection_time, 3)
                        }
                        successful += 1
                    else:
                        result = {
                            'hostname': server['hostname'],
                            'name': server['name'],
                            'success': False,
                            'error': 'Connection failed',
                            'connection_time': round(connection_time, 3)
                        }
                        failed += 1
                
                results.append(result)
                
            except Exception as e:
                result = {
                    'hostname': server['hostname'],
                    'name': server['name'],
                    'success': False,
                    'error': str(e)
                }
                results.append(result)
                failed += 1
        
        return jsonify({
            'results': results,
            'summary': {
                'total_tested': len(servers),
                'successful': successful,
                'failed': failed,
                'success_rate': round((successful / len(servers)) * 100, 1) if servers else 0
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Bulk connectivity check failed: {str(e)}'
        }), 500

@app.route('/api/server_status/<hostname>')
def api_server_status(hostname):
    """REST API endpoint to get status of a specific server"""
    try:
        # Load servers from ssh_hosts.json
        ssh_hosts_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'ssh_hosts.json')
        
        try:
            with open(ssh_hosts_file, 'r') as f:
                hosts_data = json.load(f)
                servers = hosts_data.get('hosts', [])
        except FileNotFoundError:
            return jsonify({'error': 'ssh_hosts.json file not found'}), 404
        
        # Find the server
        server = next((s for s in servers if s['hostname'] == hostname), None)
        
        if not server:
            return jsonify({'error': f'Server {hostname} not found in configuration'}), 404
        
        # Quick connectivity test
        test_client = VersaLogIQ()
        start_time = time.time()
        
        try:
            success = test_client.connect_to_server(
                hostname,
                server['user'],
                server['password']
            )
            
            connection_time = time.time() - start_time
            
            if success:
                test_client.ssh_client.close()
                status = 'online'
                error = None
            else:
                status = 'offline'
                error = 'Connection failed'
                
        except Exception as e:
            connection_time = time.time() - start_time
            status = 'offline'
            error = str(e)
        
        response = {
            'hostname': hostname,
            'name': server['name'],
            'flavor': server['flavour'],
            'status': status,
            'last_check': datetime.now().isoformat(),
            'response_time': round(connection_time, 3)
        }
        
        if error:
            response['error'] = error
            
        return jsonify(response)
        
    except Exception as e:
        return jsonify({'error': f'Status check failed: {str(e)}'}), 500

@app.route('/api/connectivity_report')
def api_connectivity_report():
    """REST API endpoint to generate comprehensive connectivity report"""
    try:
        # Load servers from ssh_hosts.json
        ssh_hosts_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'ssh_hosts.json')
        
        try:
            with open(ssh_hosts_file, 'r') as f:
                hosts_data = json.load(f)
                servers = hosts_data.get('hosts', [])
        except FileNotFoundError:
            return jsonify({'error': 'ssh_hosts.json file not found'}), 404
        
        if not servers:
            return jsonify({'error': 'No servers configured'}), 400
        
        report_servers = []
        total_servers = len(servers)
        online_servers = 0
        offline_servers = 0
        by_flavor = {}
        
        for server in servers:
            try:
                # Quick connectivity test
                test_client = VersaLogIQ()
                start_time = time.time()
                
                success = test_client.connect_to_server(
                    server['hostname'],
                    server['user'],
                    server['password']
                )
                
                connection_time = time.time() - start_time
                
                if success:
                    test_client.ssh_client.close()
                    status = 'online'
                    online_servers += 1
                else:
                    status = 'offline'
                    offline_servers += 1
                
                # Track by flavor
                flavor = server['flavour']
                if flavor not in by_flavor:
                    by_flavor[flavor] = {'total': 0, 'online': 0}
                
                by_flavor[flavor]['total'] += 1
                if status == 'online':
                    by_flavor[flavor]['online'] += 1
                
                server_info = {
                    'hostname': server['hostname'],
                    'name': server['name'],
                    'flavor': flavor,
                    'status': status,
                    'response_time': round(connection_time, 3)
                }
                
                report_servers.append(server_info)
                
            except Exception as e:
                offline_servers += 1
                flavor = server['flavour']
                if flavor not in by_flavor:
                    by_flavor[flavor] = {'total': 0, 'online': 0}
                by_flavor[flavor]['total'] += 1
                
                server_info = {
                    'hostname': server['hostname'],
                    'name': server['name'],
                    'flavor': flavor,
                    'status': 'error',
                    'error': str(e)
                }
                report_servers.append(server_info)
        
        return jsonify({
            'generated_at': datetime.now().isoformat(),
            'servers': report_servers,
            'summary': {
                'total_servers': total_servers,
                'online_servers': online_servers,
                'offline_servers': offline_servers,
                'availability_percentage': round((online_servers / total_servers) * 100, 1) if total_servers > 0 else 0,
                'by_flavor': by_flavor
            }
        })
        
    except Exception as e:
        return jsonify({'error': f'Report generation failed: {str(e)}'}), 500

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    session_id = request.sid
    print(f'Client connected with session ID: {session_id}')
    
    # Get client-specific instance
    client_versalogiq = get_client_instance()
    
    # Send the actual SSH connection status, not WebSocket status
    if client_versalogiq.connected:
        emit('connection_status', {'connected': True, 'message': 'Connected to SSH server'})
    else:
        emit('connection_status', {'connected': False, 'message': 'Not Connected'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    session_id = request.sid
    print(f'Client disconnected with session ID: {session_id}')
    
    # Clean up client instance
    cleanup_client_instance(session_id)

@socketio.on('ssh_connect')
def handle_ssh_connect(data):
    """Handle SSH connection request"""
    host = data.get('host', '')
    username = data.get('username', '')
    ssh_password = data.get('ssh_password', '')
    # Admin password is now automatically set to SSH password
    admin_password = ssh_password  # Use SSH password as admin password
    
    if not all([host, username, ssh_password]):
        emit('connection_status', {'connected': False, 'message': 'Missing connection parameters'})
        return
    
    # Get client-specific instance
    client_versalogiq = get_client_instance()
    
    # Run connection in separate thread
    thread = threading.Thread(
        target=client_versalogiq.connect_to_server,
        args=(host, username, ssh_password, admin_password),
        daemon=True
    )
    thread.start()

@socketio.on('ssh_disconnect')
def handle_ssh_disconnect():
    """Handle SSH disconnection request"""
    client_versalogiq = get_client_instance()
    client_versalogiq.disconnect_from_server()

@socketio.on('scan_logs')
def handle_scan_logs():
    """Handle log scanning request"""
    client_versalogiq = get_client_instance()
    if not client_versalogiq.connected:
        emit('log_output', {
            'message': 'Error: Not connected to server',
            'tag': 'error',
            'timestamp': datetime.now().strftime("%H:%M:%S")
        })
        return
    
    # Run log scanning in separate thread
    thread = threading.Thread(target=client_versalogiq.scan_system_logs, daemon=True)
    thread.start()

@socketio.on('get_log_file_content')
def handle_get_log_file_content(data):
    """Handle request to get log file content with filtering options"""
    client_versalogiq = get_client_instance()
    log_file_path = data.get('path', '')
    lines = data.get('lines', 250)
    log_filter = data.get('filter', 'all')  # Default to 'all'
    
    if not log_file_path:
        emit('log_file_content_response', {
            'path': log_file_path, 
            'content': {}, 
            'error': 'Missing log file path'
        })
        return
    
    if not client_versalogiq.connected:
        emit('log_file_content_response', {
            'path': log_file_path, 
            'content': {}, 
            'error': 'Not connected to server'
        })
        return
    
    session_id = request.sid
    
    # Run log file content extraction in separate thread
    def get_log_file_content():
        content = client_versalogiq.get_log_file_tail(log_file_path, lines, log_filter)
        socketio.emit('log_file_content_response', {
            'path': log_file_path,
            'content': content,
            'lines': lines,
            'filter': log_filter
        }, room=session_id)
    
    thread = threading.Thread(target=get_log_file_content, daemon=True)
    thread.start()

@socketio.on('clear_output')
def handle_clear_output():
    """Handle clear output request"""
    emit('clear_output_response', {})

if __name__ == '__main__':
    print("=" * 60)
    print("VersaLogIQ - Docker-based Log Intelligence Platform")
    print("=" * 60)
    print("A comprehensive web-based tool for server log management")
    print()
    print("Features:")
    print("  • SSH connection with automatic sudo elevation")
    print("  • Real-time log file scanning and processing") 
    print("  • System log discovery and visualization")
    print("  • Docker-based microservices architecture")
    print("  • Automatic UI reset on disconnect")
    print()
    print("Server starting...")
    print("Access via: http://localhost:5000 (direct) or http://localhost (nginx)")
    print("Health check: http://localhost:5000/health")
    print("Press Ctrl+C to stop the server")
    print("=" * 60)
    
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)