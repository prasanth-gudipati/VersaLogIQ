# VersaLogIQ Phase 2 Enhancements

## Overview
VersaLogIQ has been enhanced with MongoDB database integration and intelligent server flavor detection capabilities.

## New Features

### 1. MongoDB Database Integration
- **Purpose**: Persistent storage for server registration and connection history
- **Collections**:
  - `servers`: Server registration with flavor detection data
  - `connection_history`: Detailed connection attempt tracking

### 2. Intelligent Server Flavor Detection
Automatically detects and identifies server types:
- **VMS** (Versa Management System)
- **SCIM** (Versa SCIM API)
- **Concerto** (Versa Concerto/ECP)
- **VOS** (Versa Operating System)
- **VD** (Versa Director)
- **VAN** (Versa Analytics)

### 3. Enhanced Log Discovery
- **Flavor-specific log paths**: Uses detected server type to optimize log scanning
- **Version filtering**: Ignores latest 2 versions of log files (configurable)
- **Smart path detection**: Automatically finds relevant log directories

### 4. RESTful API Endpoints
- `GET /api/servers` - List all registered servers
- `GET /api/servers/{id}` - Get specific server information
- `GET /api/servers/{id}/history` - Get connection history
- `GET /api/database/status` - Check database health

### 5. MongoDB Express GUI
- **URL**: http://localhost:8081
- **Credentials**: admin / VersaLogIQ_Admin_Pass123
- **Features**: Direct database management and inspection

## Technical Implementation

### Server Detection Logic
```python
detection_commands = {
    'VMS': ['vsh status | grep msgservice'],
    'SCIM': ['docker ps | grep scim'],
    'Concerto': ['vsh system details | grep -i concerto'],
    'VOS': ['vsh details | grep flex'],
    'VD': ['vsh details | grep directo'],
    'VAN': ['vsh details | grep analytics']
}
```

### Database Schema

#### Servers Collection
```javascript
{
  server_identifier: String,      // IP address or FQDN
  host_type: String,             // 'IP' or 'FQDN'  
  username: String,              // SSH username
  server_flavor: String,         // Detected flavor
  flavor_detection_data: Object, // Raw detection output
  log_paths: [String],          // Relevant log paths
  connection_count: Number,      // Total connections
  created_at: Date,
  updated_at: Date,
  last_connected_at: Date,
  is_active: Boolean
}
```

#### Connection History Collection
```javascript
{
  server_identifier: String,
  session_id: String,
  username: String,
  connection_attempt_at: Date,
  connection_established_at: Date,
  disconnected_at: Date,
  status: String,               // 'CONNECTING', 'CONNECTED', 'FAILED', 'DISCONNECTED'
  failure_reason: String,
  session_duration_seconds: Number,
  log_files_scanned: Number,
  operations_performed: [String]
}
```

### Version Filtering Logic
The system applies intelligent filtering to log files:
1. Groups files by base name (removes version/date suffixes)
2. Sorts files chronologically
3. Excludes the latest 2 versions for each group
4. Focuses on historical logs for troubleshooting

**Example**:
```
Original files: app.log.1, app.log.2, app.log.3, app.log.4
After filtering: app.log.1, app.log.2 (excludes app.log.3, app.log.4)
```

## Deployment Configuration

### Docker Services Added
```yaml
mongodb:
  image: mongo:7-jammy
  environment:
    - MONGO_INITDB_ROOT_USERNAME=admin
    - MONGO_INITDB_ROOT_PASSWORD=VersaLogIQ_Root_Pass123
  volumes:
    - mongodb_data:/data/db
    - ./config/mongodb:/docker-entrypoint-initdb.d

mongo-express:
  image: mongo-express:1-20
  environment:
    - ME_CONFIG_MONGODB_ADMINUSERNAME=admin
    - ME_CONFIG_MONGODB_ADMINPASSWORD=VersaLogIQ_Root_Pass123
  ports:
    - "8081:8081"
```

## Testing the Enhancements

### 1. Database Health Check
```bash
curl http://localhost:5000/api/database/status
```

### 2. Server Registration Test
Connect to any server through the web interface - it will be automatically registered with flavor detection.

### 3. View Registered Servers
```bash
curl http://localhost:5000/api/servers
```

### 4. MongoDB Express Access
Navigate to http://localhost:8081 and login to view database contents directly.

### 5. Connection History Tracking
Each connection attempt is logged with detailed information including:
- Connection success/failure
- Session duration
- Operations performed
- Log files scanned

## Benefits

1. **Persistent Memory**: Server information persists across restarts
2. **Intelligent Routing**: Flavor detection optimizes log discovery paths
3. **Historical Tracking**: Complete audit trail of all connections
4. **Focused Analysis**: Version filtering reduces noise in log analysis
5. **Scalable Architecture**: MongoDB provides robust data management
6. **Administrative Visibility**: MongoDB Express for direct database access

## Future Enhancements

1. **Predictive Analytics**: Use connection patterns for proactive monitoring
2. **Alert Integration**: Automated notifications based on server behavior
3. **Multi-tenant Support**: Separate workspaces for different teams
4. **Advanced Filtering**: More sophisticated log version filtering rules
5. **Export Capabilities**: Generate reports from connection history data