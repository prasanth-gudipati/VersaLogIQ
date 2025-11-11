# VersaLogIQ REST API Connectivity Testing

## Overview

This document describes the REST API endpoints added to VersaLogIQ for testing connectivity to servers listed in `ssh_hosts.json`. These endpoints provide programmatic access to server connectivity testing and monitoring capabilities.

## API Endpoints

### Health and Status Endpoints

#### `GET /health`
Basic health check for the VersaLogIQ service.

**Response:**
```json
{
    "status": "healthy",
    "service": "VersaLogIQ"
}
```

#### `GET /version`
Get service version and feature information.

**Response:**
```json
{
    "service": "VersaLogIQ",
    "version": "1.0.1",
    "build_time": "2025-11-11T...",
    "features": ["SSH Connection Management", "..."]
}
```

### Connectivity Testing Endpoints

#### `POST /api/test_connection`
Test connection to a specific server.

**Request Body:**
```json
{
    "hostname": "10.73.21.106",
    "username": "admin",
    "password": "versa123",
    "key_filename": "/path/to/key.pem",  // Optional
    "expected_flavor": "VOS",           // Optional
    "use_mock": false                   // Optional
}
```

**Response:**
```json
{
    "success": true,
    "hostname": "10.73.21.106",
    "detected_flavor": "VOS",
    "sudo_available": true,
    "requires_password": false,
    "connection_time": 2.345
}
```

#### `POST /api/check_all_servers`
Test connectivity to all servers configured in `ssh_hosts.json`.

**Request Body:**
```json
{
    "use_mock": false  // Optional, use mock responses for testing
}
```

**Response:**
```json
{
    "results": [
        {
            "hostname": "10.73.21.106",
            "name": "tb2-278-sdwan-branch3",
            "success": true,
            "detected_flavor": "VOS",
            "expected_flavor": "VOS",
            "flavor_match": true,
            "sudo_available": true,
            "connection_time": 2.345
        }
    ],
    "summary": {
        "total_tested": 7,
        "successful": 6,
        "failed": 1,
        "success_rate": 85.7
    }
}
```

#### `GET /api/server_status/<hostname>`
Get current status of a specific server by hostname.

**Response:**
```json
{
    "hostname": "10.73.21.106",
    "name": "tb2-278-sdwan-branch3",
    "flavor": "VOS",
    "status": "online",
    "last_check": "2025-11-11T10:30:00",
    "response_time": 1.234
}
```

#### `GET /api/connectivity_report`
Generate comprehensive connectivity report for all configured servers.

**Response:**
```json
{
    "generated_at": "2025-11-11T10:30:00",
    "servers": [
        {
            "hostname": "10.73.21.106",
            "name": "tb2-278-sdwan-branch3",
            "flavor": "VOS",
            "status": "online",
            "response_time": 1.234
        }
    ],
    "summary": {
        "total_servers": 7,
        "online_servers": 6,
        "offline_servers": 1,
        "availability_percentage": 85.7,
        "by_flavor": {
            "VMS": {"total": 2, "online": 2},
            "VOS": {"total": 1, "online": 1},
            "SCIM": {"total": 1, "online": 1},
            "ECP": {"total": 2, "online": 2},
            "VAN": {"total": 1, "online": 0}
        }
    }
}
```

## Test Cases

### Unit Tests

The test suite includes comprehensive unit tests for each API endpoint:

1. **Basic API Tests** (`TestRESTAPIConnectivity`)
   - Health check endpoint validation
   - Version endpoint validation
   - Response format verification

2. **Server Connectivity Tests** (`TestServerConnectivityAPI`)
   - Individual server connection testing
   - Bulk connectivity testing
   - Response validation and timing

3. **Server Status Tests** (`TestServerStatusAPI`)
   - Status checking by hostname
   - Connectivity report generation
   - Summary statistics validation

4. **Mock Server Tests** (`TestMockServerConnectivity`)
   - Mock response validation
   - Performance testing with mocks
   - Error scenario testing

5. **Performance Tests** (`TestAPIPerformance`)
   - Connection time validation
   - Bulk operation performance
   - Timeout handling

6. **Error Handling Tests** (`TestAPIErrorHandling`)
   - Invalid hostname handling
   - Authentication failure handling
   - Network error scenarios

### Running Tests

```bash
# Run all API tests
cd tests
python run_tests.py --type api

# Run specific test category
python test_rest_api_connectivity.py --category basic
python test_rest_api_connectivity.py --category connectivity
python test_rest_api_connectivity.py --category mock

# Quick connectivity test
python test_api_connectivity.py

# Run with verbose output
python test_rest_api_connectivity.py --verbose
```

## Server Configuration

Tests automatically load server configurations from `ssh_hosts.json`:

```json
{
    "hosts": [
        {
            "name": "tb2-278-sdwan-branch3",
            "flavour": "VOS", 
            "hostname": "10.73.21.106",
            "user": "admin",
            "password": "versa123"
        }
    ]
}
```

## Mock Testing

For reliable testing without requiring actual server connections, the API supports mock mode:

```bash
# Test with mock responses
curl -X POST http://localhost:5000/api/test_connection \
  -H "Content-Type: application/json" \
  -d '{
    "hostname": "192.168.1.100",
    "username": "admin", 
    "password": "test123",
    "use_mock": true
  }'
```

## Integration with Test Framework

The REST API connectivity tests integrate seamlessly with the existing test framework:

```bash
# Include API tests in full test suite
python run_tests.py --coverage

# Generate test report including API tests
python run_tests.py --report api_test_results.json

# Validate test environment including API endpoints
python run_tests.py --validate
```

## Error Handling

All API endpoints include comprehensive error handling:

- **Connection Errors**: Returned as `success: false` with error details
- **Authentication Failures**: Proper HTTP status codes and error messages
- **Timeout Handling**: Configurable timeouts with appropriate responses
- **Server Not Found**: 404 responses for non-existent servers
- **Invalid JSON**: 400 responses for malformed requests

## Performance Considerations

- **Connection Timeouts**: Configurable per endpoint (5-30 seconds)
- **Bulk Operations**: Optimized for multiple server testing
- **Mock Mode**: Fast responses for development/testing
- **Concurrent Testing**: Thread-safe server testing

## Future Enhancements

1. **Authentication**: API key or token-based authentication
2. **Rate Limiting**: Prevent excessive connection attempts
3. **Caching**: Cache server status for improved performance
4. **WebSocket Updates**: Real-time connectivity status updates
5. **Metrics**: Detailed performance and reliability metrics

---

**VersaLogIQ REST API Connectivity v1.0**  
*Programmatic server connectivity testing and monitoring*