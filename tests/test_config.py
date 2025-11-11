#!/usr/bin/env python3
"""
Test configuration for VersaLogIQ test automation
"""

import os
import sys

# Add parent directory to path for imports
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TEST_DIR)
BACKEND_DIR = os.path.join(PROJECT_ROOT, 'backend')

# Add paths for imports
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, BACKEND_DIR)

# Test configuration
TEST_CONFIG = {
    'timeout': {
        'ssh_connection': 10,
        'sudo_response': 10,
        'command_execution': 15,
        'flavor_detection': 30
    },
    'mock_data': {
        'use_mock_servers': True,
        'mock_responses_file': 'mock/mock_responses.py'
    },
    'logging': {
        'level': 'INFO',
        'file': 'reports/test_results.log',
        'console': True
    },
    'coverage': {
        'enabled': True,
        'report_file': 'reports/coverage.html',
        'min_percentage': 80
    }
}

# Server flavor test configurations
FLAVOR_TEST_CONFIG = {
    'vms': {
        'name': 'VMS',
        'icon': '🎛️',
        'detection_commands': ['vsh status | grep msgservice'],
        'sudo_required': True,
        'expected_patterns': ['msgservice']
    },
    'vos': {
        'name': 'VOS', 
        'icon': '🔧',
        'detection_commands': ['vsh details', 'cat /etc/versa-release'],
        'sudo_required': False,
        'expected_patterns': ['versa-flexvnf', 'versa']
    },
    'scim': {
        'name': 'SCIM',
        'icon': '🎛️', 
        'detection_commands': ['docker ps |grep -i versa_scim'],
        'sudo_required': False,
        'expected_patterns': ['versa_scim']
    },
    'ecp': {
        'name': 'ECP',
        'icon': '🎛️',
        'detection_commands': ['vsh system details | grep concerto'],
        'sudo_required': True,
        'expected_patterns': ['concerto']
    },
    'van': {
        'name': 'VAN',
        'icon': '🎛️',
        'detection_commands': ['vsh details | grep versa-analytics'],
        'sudo_required': False,
        'expected_patterns': ['versa-analytics']
    },
    'ubuntu': {
        'name': 'Ubuntu Linux',
        'icon': '🐧',
        'detection_commands': ['lsb_release -d', 'cat /etc/os-release'],
        'sudo_required': False,
        'expected_patterns': ['ubuntu']
    }
}

# Sudo response patterns for testing
SUDO_RESPONSE_PATTERNS = {
    'password_required': [
        '[sudo] password for admin: ',
        'Password for admin:',
        'sudo password:',
        '[sudo] password for user: '
    ],
    'passwordless': [
        'admin@server:~$ sudo su\n# ',
        'versa@SCIM-QA: ~] # sudo su\nroot@SCIM-QA:/home/versa# ',
        '[user@host ~]$ sudo su\n[root@host ~]# ',
        '$ sudo su\nroot@hostname:/home/user# '
    ],
    'error_cases': [
        'sudo: command not found',
        'Permission denied',
        'sudo: unable to resolve host',
        ''  # Empty response
    ]
}

# API Testing Configuration
API_TEST_CONFIG = {
    'base_url': 'http://localhost:5000',
    'timeout': {
        'health_check': 5,
        'single_connection': 30,
        'bulk_check': 120,
        'status_check': 10,
        'report_generation': 30
    },
    'endpoints': {
        'health': '/health',
        'version': '/version',
        'test_connection': '/api/test_connection',
        'check_all_servers': '/api/check_all_servers',
        'server_status': '/api/server_status',
        'connectivity_report': '/api/connectivity_report'
    },
    'test_servers': {
        'mock_vms': {
            'hostname': '192.168.1.100',
            'username': 'admin',
            'password': 'test123',
            'expected_flavor': 'VMS',
            'use_mock': True
        },
        'mock_vos': {
            'hostname': '192.168.1.101',
            'username': 'admin',
            'password': 'test123',
            'expected_flavor': 'VOS',
            'use_mock': True
        },
        'mock_scim': {
            'hostname': '192.168.1.102',
            'username': 'versa',
            'password': 'test123',
            'expected_flavor': 'SCIM',
            'use_mock': True
        }
    }
}

# Mock server definitions
MOCK_SERVERS = {
    'vms_server': {
        'hostname': 'test-vms.local',
        'username': 'admin',
        'password': 'test123',
        'flavor': 'VMS',
        'sudo_type': 'password_required',
        'banner': 'Welcome to VMS Test Server',
        'responses': {
            'sudo su': '[sudo] password for admin: ',
            'vsh status | grep msgservice': 'msgservice: running'
        }
    },
    'scim_server': {
        'hostname': 'test-scim.local', 
        'username': 'versa',
        'password': 'test123',
        'flavor': 'SCIM',
        'sudo_type': 'passwordless',
        'banner': 'Welcome to SCIM Test Server',
        'responses': {
            'sudo su': 'versa@test-scim: ~] # sudo su\nroot@test-scim:/home/versa# ',
            'docker ps |grep -i versa_scim': 'versa_scim_container'
        }
    },
    'ubuntu_server': {
        'hostname': 'test-ubuntu.local',
        'username': 'admin', 
        'password': 'test123',
        'flavor': 'Ubuntu',
        'sudo_type': 'password_required',
        'banner': 'Welcome to Ubuntu 18.04 LTS',
        'responses': {
            'sudo su': '[sudo] password for admin: ',
            'lsb_release -d': 'Description:\tUbuntu 18.04 LTS'
        }
    }
}

# Log file test data
LOG_FILE_TEST_DATA = {
    'valid_log_files': [
        '/var/log/apache2/access.log',
        '/var/log/syslog',
        '/var/log/auth.log', 
        '/var/log/nginx/error.log',
        '/var/log/application.log.2024-11-11'
    ],
    'excluded_gz_files': [
        '/var/log/apache2/access.log.1.gz',
        '/var/log/syslog.gz',
        '/var/log/auth.log.2.gz',
        '/var/log/application.log.gz.old',
        '/var/log/test.gz.log'
    ],
    'mock_log_content': {
        'access.log': 'GET /api/test 200 1234',
        'error.log': 'ERROR: Database connection failed',
        'syslog': 'Nov 11 12:34:56 server kernel: test message'
    }
}

# Test credentials (for mock testing only)
TEST_CREDENTIALS = {
    'admin_user': {
        'username': 'admin',
        'password': 'test123',
        'admin_password': 'test123'
    },
    'versa_user': {
        'username': 'versa',
        'password': 'test123',
        'admin_password': 'test123'
    }
}

# Test environment settings
def get_test_env():
    """Get test environment configuration"""
    return {
        'project_root': PROJECT_ROOT,
        'backend_dir': BACKEND_DIR,
        'test_dir': TEST_DIR,
        'config_file': os.path.join(PROJECT_ROOT, 'config', 'server_flavors.json'),
        'ssh_hosts_file': os.path.join(PROJECT_ROOT, 'ssh_hosts.json')
    }

# Validation functions
def validate_test_config():
    """Validate test configuration is complete"""
    required_keys = ['timeout', 'mock_data', 'logging', 'coverage']
    for key in required_keys:
        if key not in TEST_CONFIG:
            raise ValueError(f"Missing required test config key: {key}")
    return True

def get_flavor_config(flavor_key):
    """Get configuration for specific server flavor"""
    return FLAVOR_TEST_CONFIG.get(flavor_key.lower())

def get_mock_server(server_key):
    """Get mock server configuration"""
    return MOCK_SERVERS.get(server_key)

def get_sudo_patterns(pattern_type):
    """Get sudo response patterns for testing"""
    return SUDO_RESPONSE_PATTERNS.get(pattern_type, [])

if __name__ == "__main__":
    # Test configuration validation
    print("🧪 VersaLogIQ Test Configuration")
    print("=" * 40)
    
    try:
        validate_test_config()
        print("✅ Test configuration is valid")
        
        env = get_test_env()
        print(f"📁 Project root: {env['project_root']}")
        print(f"📁 Backend dir: {env['backend_dir']}")
        print(f"📁 Test dir: {env['test_dir']}")
        
        print(f"\n🎛️  Server flavors configured: {len(FLAVOR_TEST_CONFIG)}")
        for flavor, config in FLAVOR_TEST_CONFIG.items():
            print(f"   {config['icon']} {config['name']}: {len(config['detection_commands'])} commands")
        
        print(f"\n🖥️  Mock servers configured: {len(MOCK_SERVERS)}")
        for server, config in MOCK_SERVERS.items():
            print(f"   {config['flavor']}: {config['hostname']} ({config['sudo_type']})")
        
        print(f"\n📝 Test patterns configured:")
        for pattern_type, patterns in SUDO_RESPONSE_PATTERNS.items():
            print(f"   {pattern_type}: {len(patterns)} patterns")
        
        print("\n✅ Configuration validation complete!")
        
    except Exception as e:
        print(f"❌ Configuration validation failed: {str(e)}")
        sys.exit(1)