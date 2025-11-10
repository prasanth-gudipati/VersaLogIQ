#!/usr/bin/env python3
"""
SSH Connectivity Tester
A comprehensive tool to test SSH connectivity to multiple hosts from a JSON configuration file.

Features:
- Load host configurations from JSON file
- Parallel or sequential testing options
- Detailed connection status reporting
- Error analysis and troubleshooting suggestions
- Summary report generation
- Export results to CSV/JSON
"""

import paramiko
import json
import sys
import time
import threading
import argparse
from datetime import datetime
import csv
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple
import re

class SSHConnectivityTester:
    def __init__(self, config_file: str = "ssh_hosts.json", flavour_config_file: str = "VersaLogIQ/config/server_flavors.json"):
        """Initialize the SSH connectivity tester"""
        self.config_file = config_file
        self.flavour_config_file = flavour_config_file
        self.hosts = []
        self.results = []
        self.start_time = None
        self.end_time = None
        self.flavour_configs = {}
        
    def load_flavour_configs(self) -> bool:
        """Load server flavour detection configurations"""
        try:
            if not os.path.exists(self.flavour_config_file):
                print(f"⚠️  Flavour config file not found: {self.flavour_config_file}")
                print("📝 Flavour detection will be skipped")
                return False
                
            with open(self.flavour_config_file, 'r') as f:
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
        
    def load_hosts(self) -> bool:
        """Load host configurations from JSON file"""
        try:
            print(f"📋 Loading host configurations from: {self.config_file}")
            
            if not os.path.exists(self.config_file):
                print(f"❌ Configuration file not found: {self.config_file}")
                return False
                
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                
            self.hosts = config.get('hosts', [])
            
            if not self.hosts:
                print("❌ No hosts found in configuration file")
                return False
                
            print(f"✅ Loaded {len(self.hosts)} host configurations")
            
            # Also load flavour detection configurations
            self.load_flavour_configs()
            
            return True
            
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON format in {self.config_file}: {str(e)}")
            return False
        except Exception as e:
            print(f"❌ Error loading configuration: {str(e)}")
            return False
    
    def execute_ssh_command(self, ssh_client, command: str, timeout: int = 15, use_sudo: bool = False) -> Tuple[str, str]:
        """Execute a command via SSH and return stdout, stderr"""
        try:
            original_command = command
            if use_sudo:
                # Check if this is a VMS-specific command that needs root shell
                if command.strip().startswith('vsh status') and 'msgservice' in command:
                    print(f"          🔐 Executing VMS command with sudo shell: {command}")
                    return self._execute_with_sudo_shell(ssh_client, command, timeout)
                else:
                    print(f"          🔐 Executing with sudo prefix: {command}")
                    return self._execute_with_sudo_prefix(ssh_client, command, timeout)
            else:
                print(f"          🔓 Executing without sudo: {command}")
            
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
                    stdin, stdout, stderr = ssh_client.exec_command(vos_cmd, timeout=timeout)
                    time.sleep(1.0)
                    
                    stdout_data = stdout.read().decode('utf-8', errors='ignore').strip()
                    stderr_data = stderr.read().decode('utf-8', errors='ignore').strip()
                    
                    # If we got output or no "command not found" error, use this result
                    if stdout_data or ("command not found" not in stderr_data and "No such file" not in stderr_data):
                        return stdout_data, stderr_data
                
                # If all VOS commands failed, return the last result
                return stdout_data, stderr_data
            else:
                stdin, stdout, stderr = ssh_client.exec_command(command, timeout=timeout)
                time.sleep(1.0)
                
                stdout_data = stdout.read().decode('utf-8', errors='ignore').strip()
                stderr_data = stderr.read().decode('utf-8', errors='ignore').strip()
                
                return stdout_data, stderr_data
            
        except Exception as e:
            return "", str(e)
    
    def _execute_with_sudo_shell(self, ssh_client, command: str, timeout: int = 15) -> Tuple[str, str]:
        """Execute a command using interactive shell with sudo su (similar to versalogiq_app.py)"""
        try:
            # Create interactive shell
            shell = ssh_client.invoke_shell()
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
            
            # Get the password from the host config (assume same as SSH password)
            # This is a simplified approach - in production, you'd want proper password management
            host_config = None
            for host in self.hosts:
                if ssh_client.get_transport().sock.getpeername()[0] == host.get('hostname'):
                    host_config = host
                    break
            
            if not host_config:
                shell.close()
                return "", "Could not find host password for sudo"
            
            # Send password
            password = host_config.get('password', '')
            shell.send(password + "\n")
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
            import re
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
    
    def _execute_with_sudo_prefix(self, ssh_client, command: str, timeout: int = 15) -> Tuple[str, str]:
        """Execute a command using sudo prefix with interactive shell (for ECP and similar systems)"""
        try:
            print(f"          🔍 Using interactive shell approach for: {command}")
            
            # Get the password from the host config
            host_config = None
            for host in self.hosts:
                if ssh_client.get_transport().sock.getpeername()[0] == host.get('hostname'):
                    host_config = host
                    break
            
            password = host_config.get('password', '') if host_config else ''
            
            # Create interactive shell (like the manual test)
            shell = ssh_client.invoke_shell()
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
            
            print(f"          📊 Raw interactive output: '{final_output}'")
            
            # Clean the output - remove ANSI codes, command echoes, and prompts
            import re
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
            
            print(f"          📋 Final cleaned output: '{result_output}'")
            
            return result_output, ""
            
        except Exception as e:
            print(f"          ❌ Interactive shell execution failed: {str(e)}")
            return "", f"Interactive sudo execution failed: {str(e)}"

    def detect_server_flavour(self, ssh_client, host_name: str) -> str:
        """Detect the actual server flavour using detection rules"""
        if not self.flavour_configs:
            return "Unknown"
        
        print(f"   🔍 Detecting server flavour for {host_name}...")
        
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
                flavour_items.append(rule)
            
            # Add fallback commands
            for rule in fallback_commands:
                rule['flavour_key'] = flavour_key
                rule['flavour_name'] = flavour_config.get('name', flavour_key)
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
                priority = rule.get('priority', 0)
                
                print(f"      🧪 Testing {flavour_name} (Priority: {priority}) - Command: {command}")
                print(f"          🔧 Use sudo: {use_sudo}")
                
                stdout, stderr = self.execute_ssh_command(ssh_client, command, timeout, use_sudo)
                
                # Debug output for VOS detection
                if 'vsh' in command.lower():
                    print(f"          📝 Command output length: {len(stdout)} chars")
                    if stdout:
                        print(f"          📝 First 200 chars: {stdout[:200]}...")
                    if stderr:
                        print(f"          ⚠️  Error output: {stderr[:200]}...")
                
                # Check if all required patterns are found
                if self.check_patterns(stdout, required_patterns, pattern_match_type, case_sensitive):
                    print(f"      ✅ Flavour detected: {flavour_name}")
                    return flavour_name
                elif stdout or stderr:
                    print(f"      ❌ Pattern not found for {flavour_name}")
                    # Debug output for pattern matching
                    if 'vsh' in command.lower() and required_patterns:
                        print(f"          🔍 Looking for patterns: {required_patterns}")
                        for pattern in required_patterns:
                            search_text = stdout if case_sensitive else stdout.lower()
                            search_pattern = pattern if case_sensitive else pattern.lower()
                            found = search_pattern in search_text
                            print(f"          🔍 Pattern '{pattern}' {'✅ FOUND' if found else '❌ NOT FOUND'}")
                else:
                    print(f"      ⚠️  No output from command for {flavour_name}")
                    
            except Exception as e:
                print(f"      ❌ Error testing {rule.get('flavour_name', 'unknown')}: {str(e)}")
                continue
        
        print(f"      ❓ No flavour detected, defaulting to Unknown")
        return "Unknown"
    
    def check_patterns(self, text: str, patterns: List[str], match_type: str = 'contains', case_sensitive: bool = False) -> bool:
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
    
    def test_single_host(self, host_config: Dict, timeout: int = 10) -> Dict:
        """Test SSH connection to a single host"""
        host_name = host_config.get('name', 'Unknown')
        hostname = host_config.get('hostname', '')
        username = host_config.get('user', '')
        password = host_config.get('password', '')
        flavour = host_config.get('flavour', 'Unknown')
        
        result = {
            'name': host_name,
            'hostname': hostname,
            'username': username,
            'flavour': flavour,
            'status': 'UNKNOWN',
            'error_type': None,
            'error_message': '',
            'response_time': 0,
            'timestamp': datetime.now().isoformat(),
            'command_test': False,
            'suggestions': []
        }
        
        start_time = time.time()
        
        try:
            print(f"🔍 Testing {host_name} ({hostname}) - Flavour: {flavour} - User: {username}")
            
            # Create SSH client
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Connect with specified timeout
            ssh.connect(
                hostname,
                username=username,
                password=password,
                timeout=timeout,
                look_for_keys=False,
                allow_agent=False,
                banner_timeout=30
            )
            
            # Calculate response time
            result['response_time'] = round(time.time() - start_time, 2)
            
            # Add delay to allow SSH session to fully stabilize
            time.sleep(2.0)
            
            # Test a simple command
            stdin, stdout, stderr = ssh.exec_command('whoami', timeout=5)
            command_output = stdout.read().decode().strip()
            command_error = stderr.read().decode().strip()
            
            if command_output and not command_error:
                result['command_test'] = True
                result['command_output'] = command_output
            
            # Add another small delay before flavour detection
            time.sleep(1.0)
            
            # Detect actual server flavour
            detected_flavour = self.detect_server_flavour(ssh, host_name)
            result['detected_flavour'] = detected_flavour
            
            # Check if detected flavour matches configured flavour
            if detected_flavour != flavour and detected_flavour != "Unknown":
                result['flavour_mismatch'] = True
                result['configured_flavour'] = flavour
                print(f"   ⚠️  Flavour mismatch! Configured: {flavour}, Detected: {detected_flavour}")
            else:
                result['flavour_mismatch'] = False
                if detected_flavour != "Unknown":
                    print(f"   ✅ Flavour confirmed: {detected_flavour}")
            
            ssh.close()
            
            result['status'] = 'SUCCESS'
            print(f"   ✅ Connection successful (Response time: {result['response_time']}s)")
            
        except paramiko.AuthenticationException as e:
            result['status'] = 'AUTH_FAILED'
            result['error_type'] = 'Authentication'
            result['error_message'] = str(e)
            result['suggestions'] = [
                'Verify username and password are correct',
                'Check if account is locked or disabled',
                'Ensure SSH service allows password authentication'
            ]
            print(f"   ❌ Authentication failed")
            
        except paramiko.ssh_exception.NoValidConnectionsError as e:
            result['status'] = 'CONNECTION_REFUSED'
            result['error_type'] = 'Connection Refused'
            result['error_message'] = str(e)
            result['suggestions'] = [
                'Check if SSH service is running on the server',
                'Verify firewall settings allow SSH (port 22)',
                'Ensure the hostname/IP is correct'
            ]
            print(f"   ❌ Connection refused")
            
        except paramiko.ssh_exception.SSHException as e:
            result['status'] = 'SSH_ERROR'
            result['error_type'] = 'SSH Protocol'
            result['error_message'] = str(e)
            result['suggestions'] = [
                'Check SSH service configuration on the server',
                'Verify SSH protocol versions are compatible'
            ]
            print(f"   ❌ SSH protocol error")
            
        except Exception as e:
            error_str = str(e).lower()
            
            if 'timeout' in error_str or 'timed out' in error_str:
                result['status'] = 'TIMEOUT'
                result['error_type'] = 'Timeout'
                result['suggestions'] = [
                    'Check network connectivity to the host',
                    'Verify the server is responding',
                    'Consider increasing timeout value'
                ]
                print(f"   ❌ Connection timeout")
            elif 'name or service not known' in error_str:
                result['status'] = 'DNS_ERROR'
                result['error_type'] = 'DNS Resolution'
                result['suggestions'] = [
                    'Verify hostname spelling',
                    'Check DNS server configuration',
                    'Try using IP address instead of hostname'
                ]
                print(f"   ❌ DNS resolution failed")
            else:
                result['status'] = 'UNKNOWN_ERROR'
                result['error_type'] = 'Unknown'
                result['suggestions'] = [
                    'Review network connectivity',
                    'Check server accessibility',
                    'Contact system administrator'
                ]
                print(f"   ❌ Unexpected error: {str(e)}")
            
            result['error_message'] = str(e)
        
        finally:
            result['response_time'] = round(time.time() - start_time, 2)
        
        return result
    
    def test_all_hosts_sequential(self, timeout: int = 10) -> None:
        """Test all hosts sequentially"""
        print(f"\n🚀 Starting sequential SSH connectivity tests...")
        print(f"📊 Total hosts to test: {len(self.hosts)}")
        print(f"⏱️  Connection timeout: {timeout}s")
        print("=" * 70)
        
        self.start_time = datetime.now()
        
        for i, host_config in enumerate(self.hosts, 1):
            print(f"\n[{i}/{len(self.hosts)}]", end=" ")
            result = self.test_single_host(host_config, timeout)
            self.results.append(result)
        
        self.end_time = datetime.now()
    
    def test_all_hosts_parallel(self, timeout: int = 10, max_workers: int = 5) -> None:
        """Test all hosts in parallel using ThreadPoolExecutor"""
        print(f"\n🚀 Starting parallel SSH connectivity tests...")
        print(f"📊 Total hosts to test: {len(self.hosts)}")
        print(f"⏱️  Connection timeout: {timeout}s")
        print(f"🧵 Max parallel connections: {max_workers}")
        print("=" * 70)
        
        self.start_time = datetime.now()
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_host = {
                executor.submit(self.test_single_host, host_config, timeout): host_config 
                for host_config in self.hosts
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_host):
                result = future.result()
                self.results.append(result)
        
        # Sort results by hostname for consistent output
        self.results.sort(key=lambda x: x['hostname'])
        self.end_time = datetime.now()
    
    def print_summary_report(self) -> None:
        """Print a detailed summary report"""
        if not self.results:
            print("❌ No test results available")
            return
        
        total_tests = len(self.results)
        successful = len([r for r in self.results if r['status'] == 'SUCCESS'])
        failed = total_tests - successful
        
        duration = (self.end_time - self.start_time).total_seconds() if self.start_time and self.end_time else 0
        
        print("\n" + "=" * 80)
        print("📊 SSH CONNECTIVITY TEST SUMMARY REPORT")
        print("=" * 80)
        print(f"🕐 Test Duration: {duration:.2f} seconds")
        print(f"📋 Total Hosts Tested: {total_tests}")
        print(f"✅ Successful Connections: {successful}")
        print(f"❌ Failed Connections: {failed}")
        print(f"📈 Success Rate: {(successful/total_tests*100):.1f}%")
        
        if successful > 0:
            avg_response_time = sum(r['response_time'] for r in self.results if r['status'] == 'SUCCESS') / successful
            print(f"⚡ Average Response Time: {avg_response_time:.2f}s")
        
        # Flavour breakdown
        flavour_stats = {}
        for result in self.results:
            flavour = result.get('flavour', 'Unknown')
            if flavour not in flavour_stats:
                flavour_stats[flavour] = {'total': 0, 'success': 0}
            flavour_stats[flavour]['total'] += 1
            if result['status'] == 'SUCCESS':
                flavour_stats[flavour]['success'] += 1
        
        print(f"\n🏷️  FLAVOUR BREAKDOWN (Configured):")
        for flavour, stats in sorted(flavour_stats.items()):
            success_rate = (stats['success'] / stats['total'] * 100) if stats['total'] > 0 else 0
            print(f"   {flavour}: {stats['success']}/{stats['total']} ({success_rate:.0f}%)")
        
        # Flavour detection summary
        detection_stats = {'detected': 0, 'mismatches': 0, 'unknown': 0}
        detected_flavours = {}
        
        for result in self.results:
            if result['status'] == 'SUCCESS':
                detected_flavour = result.get('detected_flavour', 'Unknown')
                flavour_mismatch = result.get('flavour_mismatch', False)
                
                if detected_flavour == 'Unknown':
                    detection_stats['unknown'] += 1
                else:
                    detection_stats['detected'] += 1
                    if detected_flavour not in detected_flavours:
                        detected_flavours[detected_flavour] = 0
                    detected_flavours[detected_flavour] += 1
                    
                if flavour_mismatch:
                    detection_stats['mismatches'] += 1
        
        if successful > 0:
            print(f"\n🔍 FLAVOUR DETECTION RESULTS:")
            print(f"   ✅ Successfully Detected: {detection_stats['detected']}/{successful} ({detection_stats['detected']/successful*100:.0f}%)")
            print(f"   ❓ Unknown/Failed Detection: {detection_stats['unknown']}/{successful} ({detection_stats['unknown']/successful*100:.0f}%)")
            print(f"   ⚠️  Configuration Mismatches: {detection_stats['mismatches']}/{successful} ({detection_stats['mismatches']/successful*100:.0f}%)")
            
            if detected_flavours:
                print(f"\n🏷️  DETECTED FLAVOUR BREAKDOWN:")
                for flavour, count in sorted(detected_flavours.items()):
                    print(f"   {flavour}: {count} hosts")
        
        print("\n" + "─" * 80)
        print("📝 DETAILED RESULTS")
        print("─" * 80)
        
        # Group results by status
        status_groups = {}
        for result in self.results:
            status = result['status']
            if status not in status_groups:
                status_groups[status] = []
            status_groups[status].append(result)
        
        # Print successful connections
        if 'SUCCESS' in status_groups:
            print(f"\n✅ SUCCESSFUL CONNECTIONS ({len(status_groups['SUCCESS'])})")
            print("─" * 40)
            for result in status_groups['SUCCESS']:
                configured_flavour = result.get('flavour', 'Unknown')
                detected_flavour = result.get('detected_flavour', 'Unknown')
                flavour_mismatch = result.get('flavour_mismatch', False)
                
                if flavour_mismatch:
                    flavour_display = f"⚠️ {configured_flavour}→{detected_flavour}"
                elif detected_flavour != 'Unknown':
                    flavour_display = f"✅ {detected_flavour}"
                else:
                    flavour_display = f"❓ {configured_flavour}"
                    
                print(f"   🟢 {result['name']} ({result['hostname']}) - {flavour_display} - {result['response_time']}s")
        
        # Print failed connections with details
        failed_statuses = [k for k in status_groups.keys() if k != 'SUCCESS']
        if failed_statuses:
            print(f"\n❌ FAILED CONNECTIONS ({sum(len(status_groups[s]) for s in failed_statuses)})")
            print("─" * 40)
            
            for status in failed_statuses:
                for result in status_groups[status]:
                    print(f"   🔴 {result['name']} ({result['hostname']}) - {result['flavour']}")
                    print(f"      Error Type: {result['error_type']}")
                    print(f"      Error: {result['error_message']}")
                    if result['suggestions']:
                        print(f"      Suggestions:")
                        for suggestion in result['suggestions']:
                            print(f"        • {suggestion}")
                    print()
    
    def export_results_csv(self, filename: str = None) -> str:
        """Export results to CSV file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ssh_test_results_{timestamp}.csv"
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'name', 'hostname', 'username', 'flavour', 'detected_flavour', 'flavour_mismatch',
                    'status', 'error_type', 'error_message', 'response_time', 'command_test', 'timestamp'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for result in self.results:
                    # Create a clean copy for CSV export
                    csv_row = {k: v for k, v in result.items() if k in fieldnames}
                    writer.writerow(csv_row)
            
            print(f"\n💾 Results exported to CSV: {filename}")
            return filename
            
        except Exception as e:
            print(f"❌ Error exporting to CSV: {str(e)}")
            return None
    
    def export_results_json(self, filename: str = None) -> str:
        """Export results to JSON file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ssh_test_results_{timestamp}.json"
        
        try:
            export_data = {
                'test_summary': {
                    'total_hosts': len(self.results),
                    'successful': len([r for r in self.results if r['status'] == 'SUCCESS']),
                    'failed': len([r for r in self.results if r['status'] != 'SUCCESS']),
                    'start_time': self.start_time.isoformat() if self.start_time else None,
                    'end_time': self.end_time.isoformat() if self.end_time else None,
                    'duration_seconds': (self.end_time - self.start_time).total_seconds() if self.start_time and self.end_time else 0
                },
                'results': self.results
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            print(f"💾 Results exported to JSON: {filename}")
            return filename
            
        except Exception as e:
            print(f"❌ Error exporting to JSON: {str(e)}")
            return None

def main():
    """Main function with command line argument parsing"""
    parser = argparse.ArgumentParser(
        description='SSH Connectivity Tester for multiple hosts',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s                                    # Test all hosts with default settings
  %(prog)s -c my_hosts.json                   # Use custom config file
  %(prog)s -p -w 10                           # Parallel testing with 10 workers
  %(prog)s -t 30 --export-csv                 # 30s timeout and export CSV
  %(prog)s --export-json --no-summary         # Export JSON without summary
        '''
    )
    
    parser.add_argument('-c', '--config', default='ssh_hosts.json',
                       help='JSON configuration file (default: ssh_hosts.json)')
    parser.add_argument('-f', '--flavour-config', default='VersaLogIQ/config/server_flavors.json',
                       help='Flavour detection configuration file (default: VersaLogIQ/config/server_flavors.json)')
    parser.add_argument('-t', '--timeout', type=int, default=10,
                       help='SSH connection timeout in seconds (default: 10)')
    parser.add_argument('-p', '--parallel', action='store_true',
                       help='Run tests in parallel instead of sequential')
    parser.add_argument('-w', '--workers', type=int, default=5,
                       help='Max parallel workers for parallel mode (default: 5)')
    parser.add_argument('--export-csv', action='store_true',
                       help='Export results to CSV file')
    parser.add_argument('--export-json', action='store_true',
                       help='Export results to JSON file')
    parser.add_argument('--no-summary', action='store_true',
                       help='Skip printing summary report')
    parser.add_argument('--csv-file', type=str,
                       help='Custom CSV export filename')
    parser.add_argument('--json-file', type=str,
                       help='Custom JSON export filename')
    
    args = parser.parse_args()
    
    print("🔧 SSH Connectivity Tester")
    print("=" * 50)
    
    # Initialize tester
    tester = SSHConnectivityTester(args.config, args.flavour_config)
    
    # Load host configurations
    if not tester.load_hosts():
        sys.exit(1)
    
    # Run tests
    try:
        if args.parallel:
            tester.test_all_hosts_parallel(timeout=args.timeout, max_workers=args.workers)
        else:
            tester.test_all_hosts_sequential(timeout=args.timeout)
        
        # Print summary report
        if not args.no_summary:
            tester.print_summary_report()
        
        # Export results
        if args.export_csv:
            tester.export_results_csv(args.csv_file)
        
        if args.export_json:
            tester.export_results_json(args.json_file)
        
        # Return appropriate exit code
        failed_count = len([r for r in tester.results if r['status'] != 'SUCCESS'])
        if failed_count > 0:
            print(f"\n⚠️  Warning: {failed_count} host(s) failed connectivity test")
            sys.exit(1)
        else:
            print(f"\n🎉 All hosts passed connectivity test!")
            sys.exit(0)
            
    except KeyboardInterrupt:
        print(f"\n\n⛔ Test interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Unexpected error during testing: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()