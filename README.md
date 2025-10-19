# VersaLogIQ - Log Intelligence Platform

A comprehensive Docker-based microservices application for connecting to servers and processing log files with real-time command execution display and intelligent log analysis capabilities.

## 🚀 Features

### Core Functionality
- **SSH Connection Management**: Secure connection to servers with automatic sudo elevation
- **Real-time Log Processing**: Live streaming of log file scanning and content display
- **System Log Discovery**: Automatic discovery and categorization of log files
- **Docker-based Architecture**: Containerized deployment with microservices design
- **Interactive UI**: Progressive disclosure of features based on connection state
- **Automatic Reset**: Complete UI cleanup on disconnect for fresh user experience

### Supported Operations

#### 1. SSH Server Connection
- Secure SSH authentication with password-based login
- Automatic sudo elevation for privileged operations
- Real-time connection status with detailed error analysis
- Comprehensive error popup with troubleshooting suggestions

#### 2. System Log Scanning
- Recursive scanning of `/var/log` directory and subdirectories
- Automatic categorization by directory structure
- Exclusion of compressed (.gz) files for performance
- Real-time progress display during scanning operations

#### 3. Log File Analysis
- Display last N lines of any discovered log file (100-1000 lines)
- Real-time content streaming with formatted display
- Pop-out window functionality for detailed analysis
- Command execution tracking and logging

## 🏗️ Architecture

### Docker Microservices Design
```
VersaLogIQ/
├── backend/                    # Flask-SocketIO application
│   ├── versalogiq_app.py      # Main application logic
│   ├── templates/             # HTML templates
│   ├── logs/                  # Application logs
│   └── requirements.txt       # Python dependencies
├── config/                    # Configuration files
│   └── nginx/                # Nginx proxy configuration
├── Dockerfile                # Backend container definition
├── docker-compose.yml        # Multi-service orchestration
└── .dockerignore             # Docker build exclusions
```

### Services Architecture
- **versalogiq-backend**: Main Flask-SocketIO application (Port 5000)
- **redis**: Session management and caching (Port 6379)
- **nginx**: Reverse proxy and load balancer (Ports 80/443)

## 🔧 Technical Stack

### Backend Components
- **Flask-SocketIO**: Real-time WebSocket communication
- **Paramiko**: SSH client for secure server connections
- **Docker**: Containerization and orchestration
- **Redis**: Session storage and caching
- **Nginx**: Reverse proxy and SSL termination

### Frontend Components
- **Socket.IO Client**: Real-time communication with backend
- **Progressive UI**: Dynamic show/hide based on application state
- **Event-driven Architecture**: Responsive to user actions and server events
- **State Management**: Automatic UI reset and cleanup

## 📋 Prerequisites

### System Requirements
- **OS**: Ubuntu 22.04.5 LTS (or compatible Linux distribution)
- **Docker**: Version 28.3.3 or later
- **Docker Compose**: Version 1.29.2 or later
- **RAM**: Minimum 2GB, recommended 4GB+
- **Disk**: Minimum 1GB free space

### Network Requirements
- SSH access to target servers (port 22)
- Outbound internet access for Docker image downloads
- Local network access for container communication

## 🚀 Installation & Deployment

### 1. Clone or Copy the Application
```bash
# Ensure the VersaLogIQ directory exists with all files
cd /home/versa/pgudipati/SAMBA-70-188-169/VersaLogIQ
```

### 2. Verify Docker Installation
```bash
docker --version
docker-compose --version
```

### 3. Build and Start Services
```bash
# Build and start all services
docker-compose up -d --build

# View service status
docker-compose ps

# View logs
docker-compose logs -f versalogiq-backend
```

### 4. Access the Application
- **Direct Backend**: http://localhost:5000
- **Via Nginx Proxy**: http://localhost
- **Health Check**: http://localhost:5000/health

### 5. Stop Services
```bash
# Stop all services
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

## 🎯 Usage Instructions

### 1. Initial Connection
1. Open web browser to http://localhost
2. Enter server credentials:
   - **Server IP**: Target server hostname or IP address
   - **Username**: SSH username (typically 'admin' or 'root')
   - **SSH Password**: User's SSH password
   - **Admin Password**: Password for sudo elevation
3. Click "Connect" button
4. Monitor real-time connection progress in output panel

### 2. Log File Operations
1. After successful connection, log scanning starts automatically
2. Wait for "Log file scanning completed" message
3. Select log file from dropdown in "System Logs" section
4. Choose number of lines to display (100-1000)
5. Click "View Log Content" to display file contents
6. Use "⧉" button to open content in new window

### 3. Error Handling
- Connection errors display detailed popup with troubleshooting steps
- Technical details available via expandable sections
- Copy error details to clipboard for support tickets
- Automatic UI reset on disconnect

### 4. Clean Disconnect
1. Click "Disconnect" button to terminate SSH session
2. UI automatically resets to initial state
3. All sections hidden and dropdowns cleared
4. Ready for new connection

## ⚙️ Configuration

### Environment Variables
```bash
# Backend service configuration
FLASK_ENV=production
PYTHONUNBUFFERED=1
LOG_LEVEL=INFO
```

### Server Defaults
Update these values in `backend/templates/index.html`:
```javascript
// Default connection values
value="192.168.1.100"    // Server IP
value="admin"            // Username
```

### Docker Configuration
Modify `docker-compose.yml` for:
- Port mappings
- Volume mounts
- Resource limits
- Network configuration

## 🔒 Security Considerations

### SSH Security
- Password-based authentication (consider key-based for production)
- Automatic sudo elevation with stored credentials
- SSH client auto-accepts host keys (verify for production)

### Network Security  
- Services run on localhost interfaces
- No HTTPS encryption (add SSL for production)
- No authentication on web interface (add auth for production)

### Data Security
- SSH credentials transmitted via WebSocket (encrypt for production)
- Log files persisted in Docker volumes
- Application logs stored in `backend/logs/` directory

## 📊 Monitoring & Troubleshooting

### Health Checks
```bash
# Check service health
curl http://localhost:5000/health

# View container status
docker-compose ps

# Monitor real-time logs
docker-compose logs -f
```

### Common Issues

#### Connection Problems
```bash
# Check container networking
docker network ls
docker network inspect versalogiq_versalogiq-network

# Test backend connectivity
curl -I http://localhost:5000
```

#### Log File Access
```bash
# Check backend logs
docker-compose logs versalogiq-backend

# Access container shell
docker-compose exec versalogiq-backend bash
```

#### Performance Issues
```bash
# Monitor resource usage
docker stats

# Check disk usage
docker system df
```

## 🔄 Development & Maintenance

### Code Structure
- **versalogiq_app.py**: Main application logic and SSH handling
- **index.html**: Frontend UI with Socket.IO integration
- **Dockerfile**: Backend service containerization
- **docker-compose.yml**: Multi-service orchestration

### Key Classes and Methods
- `VersaLogIQ`: Main application class
- `connect_to_server()`: SSH connection management
- `scan_system_logs()`: Log file discovery
- `get_log_file_tail()`: Log content retrieval

### Adding Features
1. Extend backend functionality in `versalogiq_app.py`
2. Add new socket events for real-time communication
3. Update frontend UI in `index.html`
4. Rebuild containers: `docker-compose up -d --build`

### Backup & Recovery
```bash
# Backup persistent data
docker-compose down
tar -czf versalogiq-backup.tar.gz backend/logs/

# Restore from backup
tar -xzf versalogiq-backup.tar.gz
docker-compose up -d
```

## 📈 Performance Optimization

### Resource Limits
```yaml
# In docker-compose.yml
services:
  versalogiq-backend:
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
```

### Log Rotation
```bash
# Configure log rotation for persistent logs
echo "backend/logs/*.log {
  daily
  rotate 7
  compress
  missingok
  notifempty
}" > /etc/logrotate.d/versalogiq
```

## 🆘 Support & Troubleshooting

### Support Channels
- Internal documentation and knowledge base
- Development team contact via internal systems
- Issue tracking via project management tools

### Diagnostic Commands
```bash
# Full system check
docker-compose ps
docker-compose logs
curl http://localhost:5000/health
ss -tuln | grep -E '(5000|80|6379)'
```

### Log Collection
```bash
# Collect all logs for analysis
mkdir versalogiq-diagnostics
docker-compose logs > versalogiq-diagnostics/docker-compose.log
docker logs versalogiq-backend > versalogiq-diagnostics/backend.log
tar -czf versalogiq-diagnostics.tar.gz versalogiq-diagnostics/
```

## 📄 License & Compliance

This application is part of the internal tools suite. Usage should comply with:
- Internal security policies
- SSH access guidelines  
- Log data handling procedures
- Docker deployment standards

---

**VersaLogIQ v1.0** - Docker-based Log Intelligence Platform  
Built with ❤️ using Flask-SocketIO, Docker, and modern web technologies.