# VersaLogIQ Test Automation Framework

## Overview

Comprehensive test automation framework for VersaLogIQ log intelligence platform, providing unit tests, integration tests, mock server responses, and automated test execution with coverage analysis.

## Test Framework Structure

```
tests/
├── run_tests.py                           # Main test runner
├── test_config.py                         # Test configuration and settings
├── README.md                             # This documentation
├── unit/                                 # Unit tests
│   ├── __init__.py
│   ├── test_flavor_detection.py         # Flavor detection unit tests
│   └── test_ssh_connection.py           # SSH connection unit tests
├── integration/                          # Integration tests
│   ├── __init__.py
│   └── test_versalogiq_workflow.py      # End-to-end workflow tests
└── mock/                                 # Mock responses and test data
    ├── __init__.py
    └── mock_responses.py                 # Mock SSH responses for testing
```

## Features

### 🧪 Comprehensive Testing
- **Unit Tests**: Test individual components (flavor detection, SSH connections)
- **Integration Tests**: Test complete workflows and component interactions
- **Mock Testing**: Simulate server responses without requiring actual servers
- **Performance Tests**: Validate response times and resource usage

### 🎯 Server Flavor Coverage
- **VMS (Versa Management System)**: Complete workflow testing
- **VOS (Versa Operating System)**: FlexVNF command testing
- **SCIM (System for Cross-domain Identity Management)**: Docker container testing
- **ECP (Enterprise Cloud Platform)**: Edge computing platform testing
- **VAN (Versa Access Node)**: Branch office testing
- **Ubuntu Linux**: Generic Linux server testing

### 🔧 Advanced Features
- **Code Coverage Analysis**: Detailed coverage reporting with missing line detection
- **Mock SSH Responses**: Realistic server response simulation
- **Sudo Testing**: Both password-required and passwordless sudo scenarios
- **Error Handling**: Comprehensive error scenario testing
- **WebSocket Testing**: Real-time communication validation
- **Performance Monitoring**: Execution time analysis

## Quick Start

### Prerequisites

```bash
# Required Python packages
pip install paramiko unittest2

# Optional for coverage analysis
pip install coverage
```

### Running Tests

```bash
# Run all tests
python run_tests.py

# Run with verbose output
python run_tests.py --verbose

# Run only unit tests
python run_tests.py --type unit

# Run only integration tests
python run_tests.py --type integration

# Run with code coverage
python run_tests.py --coverage

# Validate test environment
python run_tests.py --validate

# Run specific test
python run_tests.py --test unit/test_flavor_detection.py

# Generate detailed report
python run_tests.py --report test_report.json
```

## Test Categories

### Unit Tests

#### Flavor Detection Tests (`test_flavor_detection.py`)
- Pattern matching validation for all server types
- Priority-based detection logic testing
- Case sensitivity and pattern verification
- Error handling for unknown flavors
- Command execution mock testing

```python
# Example: Test VMS flavor detection
def test_vms_flavor_detection(self):
    mock_execute.return_value = ("msgservice: running", "")
    detected_flavor = self.versalogiq.detect_server_flavour()
    self.assertEqual(detected_flavor, "VMS")
```

#### SSH Connection Tests (`test_ssh_connection.py`)
- Connection establishment and authentication
- Private key and password authentication
- Sudo detection (password-required vs passwordless)
- Command execution with timeout handling
- Error scenarios and connection failures

```python
# Example: Test passwordless sudo detection
def test_sudo_pattern_detection_passwordless(self):
    test_patterns = ["uid=0(root) gid=0(root)", "root"]
    for pattern in test_patterns:
        needs_password, needs_sudo = self.versalogiq.check_sudo_requirements(pattern)
        self.assertFalse(needs_password)
```

### Integration Tests

#### Complete Workflow Tests (`test_versalogiq_workflow.py`)
- End-to-end server connection and flavor detection
- Multi-step workflows with error handling
- WebSocket event validation
- Log scanning with .gz exclusion testing
- Performance benchmarking

```python
# Example: Complete VMS workflow test
def test_complete_vms_workflow(self):
    # Connect → Detect Flavor → Test Sudo → Scan Logs
    connection_result = self.versalogiq.connect_to_server(...)
    detected_flavor = self.versalogiq.detect_server_flavour()
    sudo_info = self.versalogiq.test_sudo_access()
    log_files = self.versalogiq.scan_system_logs()
```

### Mock Testing

#### Mock Response System (`mock_responses.py`)
- Realistic SSH client simulation
- Server-specific response patterns
- Command-based response matching
- Sudo scenario simulation

```python
# Example: Create mock VMS server
mock_config = create_mock_server('VMS')
response_generator = FlavorResponseGenerator(mock_config)
stdout, stderr = response_generator.get_response("vsh status")
```

## Test Configuration

### Server Configurations (`test_config.py`)

```python
FLAVOR_TEST_CONFIG = {
    'VMS': {
        'priority': 1,
        'detection_commands': ['vsh status | grep msgservice'],
        'expected_patterns': ['msgservice'],
        'sudo_type': 'password_required'
    },
    'SCIM': {
        'priority': 2,
        'detection_commands': ['docker ps | grep versa_scim'],
        'expected_patterns': ['versa_scim'],
        'sudo_type': 'passwordless'
    }
}
```

### Mock Server Responses

```python
MOCK_SERVERS = {
    'VMS': {
        'flavor': 'VMS',
        'sudo_type': 'password_required',
        'responses': {
            'vsh status': 'msgservice: running (pid: 1234)',
            'sudo whoami': '[sudo] password for admin:'
        }
    }
}
```

## Advanced Usage

### Custom Test Development

```python
# Create new unit test
class TestCustomFeature(unittest.TestCase):
    def setUp(self):
        self.versalogiq = VersaLogIQ()
    
    def test_custom_functionality(self):
        # Test implementation
        result = self.versalogiq.custom_method()
        self.assertEqual(result, expected_value)
```

### Mock Server Creation

```python
# Create custom mock server
def create_custom_mock_server(flavor, custom_responses):
    mock_config = create_mock_server(flavor)
    mock_config['responses'].update(custom_responses)
    return mock_config
```

### Performance Testing

```python
# Add performance validation
def test_performance_requirement(self):
    start_time = time.time()
    result = self.versalogiq.expensive_operation()
    execution_time = time.time() - start_time
    
    self.assertLess(execution_time, 5.0)  # Must complete in < 5 seconds
```

## Test Execution Options

### Command Line Arguments

```bash
# Test type selection
--type all|unit|integration    # Select test category
--pattern "test_*.py"         # Custom test file pattern
--test specific_test.py       # Run specific test file

# Output and reporting
--verbose                     # Detailed output
--coverage                   # Code coverage analysis
--report filename.json       # Generate JSON report

# Environment and validation
--validate                   # Check test environment
--quick                     # Skip performance tests
```

### Environment Variables

```bash
# Quick test mode (skips performance tests)
export QUICK_TESTS=1

# Custom test timeout
export TEST_TIMEOUT=30

# Debug mode for mock responses
export DEBUG_MOCKS=1
```

## Coverage Analysis

### Coverage Report Example

```
Name                                    Stmts   Miss  Cover   Missing
---------------------------------------------------------------------
backend/versalogiq_app.py                 245     12    95%   123-125, 234
config/server_flavors.json                  0      0   100%
---------------------------------------------------------------------
TOTAL                                     245     12    95%
```

### Coverage Targets
- **Unit Tests**: > 90% coverage
- **Integration Tests**: > 85% coverage
- **Overall**: > 90% coverage

## Continuous Integration

### GitHub Actions Example

```yaml
name: VersaLogIQ Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.8
      - name: Install dependencies
        run: pip install -r requirements.txt coverage
      - name: Run tests
        run: cd tests && python run_tests.py --coverage --report results.json
      - name: Upload coverage
        uses: codecov/codecov-action@v1
```

## Troubleshooting

### Common Issues

1. **Module Import Errors**
   ```bash
   # Ensure PYTHONPATH includes backend directory
   export PYTHONPATH="${PYTHONPATH}:./backend:./tests"
   ```

2. **SSH Connection Mocking**
   ```python
   # Use proper mock patching
   @patch('paramiko.SSHClient')
   def test_ssh_function(self, mock_ssh_class):
       mock_client = Mock()
       mock_ssh_class.return_value = mock_client
   ```

3. **Coverage Analysis Issues**
   ```bash
   # Install coverage module
   pip install coverage
   
   # Run with coverage
   python run_tests.py --coverage
   ```

### Debug Mode

```python
# Enable debug logging in tests
import logging
logging.basicConfig(level=logging.DEBUG)

# Use debug mode for mock responses
os.environ['DEBUG_MOCKS'] = '1'
```

## Best Practices

### Test Organization
- **One test case per functionality**
- **Clear, descriptive test names**
- **Proper setup and teardown**
- **Mock external dependencies**

### Test Data Management
- **Use configuration files for test data**
- **Create reusable mock responses**
- **Isolate test environments**

### Performance Considerations
- **Mock expensive operations**
- **Use quick mode for development**
- **Profile slow tests**
- **Optimize test execution order**

## Contributing

### Adding New Tests

1. **Create test file** in appropriate directory
2. **Follow naming convention**: `test_*.py`
3. **Add configuration** to `test_config.py`
4. **Update mock responses** if needed
5. **Document test purpose** and expectations

### Test Review Checklist

- [ ] Test covers both success and failure scenarios
- [ ] Proper mocking of external dependencies
- [ ] Clear assertions with meaningful error messages
- [ ] Performance considerations addressed
- [ ] Documentation updated

## Support

### Getting Help
- Review existing test examples
- Check troubleshooting section
- Enable debug mode for detailed output
- Use verbose mode for test execution details

### Reporting Issues
- Include test environment details
- Provide test execution output
- Specify expected vs actual behavior
- Include relevant configuration

---

**VersaLogIQ Test Automation Framework v1.0**  
*Comprehensive testing for reliable log intelligence*