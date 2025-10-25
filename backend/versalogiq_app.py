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
        
        # Queue for thread communication
        self.output_queue = queue.Queue()
        
        # Create Logs directory if it doesn't exist
        self.logs_dir = "logs"
        self._ensure_logs_directory()
        
        # Setup persistent log file
        self.persistent_log_file = os.path.join(self.logs_dir, "versalogiq.log")
        
        # Initialize log file if it doesn't exist
        self._initialize_log_file()
    
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
            
            # Wait for password prompt
            buff = ""
            start_time = time.time()
            while time.time() - start_time < 10:  # 10 second timeout
                if self.shell.recv_ready():
                    resp = self.shell.recv(1000).decode('utf-8', errors='ignore')
                    buff += resp
                    if "password for" in buff.lower():
                        break
                time.sleep(0.2)
            
            if "password for" not in buff.lower():
                raise Exception("Sudo password prompt not found")
            
            # Send admin password
            self.shell.send(admin_password + "\n")
            time.sleep(1.5)
            
            # Check if sudo was successful
            output = self.shell.recv(10000).decode('utf-8', errors='ignore')
            self.log_output("Sudo elevation successful", "success")
            
            # Update connection state
            self.connected = True
            if self.session_id:
                socketio.emit('connection_status', {'connected': True, 'message': 'Connected successfully'}, room=self.session_id)
            else:
                socketio.emit('connection_status', {'connected': True, 'message': 'Connected successfully'})
            
            # Automatically start log scanning after successful connection
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
            self.log_output("Scanning for log files in /var/log directory", "info")
            
            # Execute find command to get all log files, excluding .gz files
            command = "find /var/log -type f -name '*.log*' ! -name '*.gz' | sort"
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
                
                # Check if it's a valid log file path and exclude .gz files
                if (line.startswith('/var/log/') and 
                    ('log' in line.lower()) and 
                    not line.endswith('.gz')):
                    # Extract directory and filename
                    path_parts = line.split('/')
                    if len(path_parts) >= 3:  # /var/log/[directory]/[filename] or /var/log/[filename]
                        if len(path_parts) == 3:  # Direct file in /var/log
                            directory = 'var-log-root'
                        else:
                            directory = path_parts[3] if len(path_parts) > 3 else 'var-log-root'
                        filename = path_parts[-1]
                        
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
            self.log_output(f"-> Found {total_files} log files across {total_dirs} directories (excluding .gz files)", "success")
            
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
    
    def get_log_file_tail(self, log_file_path, lines=250):
        """Get the last N lines of a log file"""
        if not self.connected:
            self.log_output("Error: Not connected to server", "error")
            return None
        
        try:
            self.log_output(f"Getting last {lines} lines from: {log_file_path}", "info")
            
            # Build command
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
    """Handle request to get log file content"""
    client_versalogiq = get_client_instance()
    log_file_path = data.get('path', '')
    lines = data.get('lines', 250)
    
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
        content = client_versalogiq.get_log_file_tail(log_file_path, lines)
        socketio.emit('log_file_content_response', {
            'path': log_file_path,
            'content': content,
            'lines': lines
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