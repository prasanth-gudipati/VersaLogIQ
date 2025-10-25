#!/bin/bash

# VersaLogIQ Deployment Script
# This script helps deploy and manage the VersaLogIQ Docker-based application

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker first."
        exit 1
    fi
    print_success "Docker is running"
}

# Function to check if docker-compose is available
check_docker_compose() {
    if ! command -v docker-compose &> /dev/null; then
        print_error "docker-compose is not installed. Please install docker-compose first."
        exit 1
    fi
    print_success "docker-compose is available"
}

# Function to show help
show_help() {
    echo "VersaLogIQ Deployment Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  start       Build and start all services"
    echo "  stop        Stop all services"
    echo "  restart     Restart all services"
    echo "  status      Show service status"
    echo "  logs        Show service logs"
    echo "  clean       Stop services and remove containers/volumes"
    echo "  update      Pull latest images, rebuild, and restart with verification"
    echo "  changes     Check for code changes and git status"
    echo "  health      Check application health"
    echo "  help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 start              # Start VersaLogIQ"
    echo "  $0 changes            # Check for code changes"
    echo "  $0 update             # Update with rebuild and verification"
    echo "  $0 logs versalogiq-backend  # Show backend logs"
    echo "  $0 clean              # Clean shutdown and cleanup"
}

# Function to start services
start_services() {
    print_status "Starting VersaLogIQ services..."
    
    check_docker
    check_docker_compose
    
    # Build and start services
    docker-compose up -d --build
    
    # Wait a moment for services to start
    sleep 5
    
    # Check status
    docker-compose ps
    
    print_success "VersaLogIQ services started successfully!"
    print_status "Access the application at:"
    print_status "  • Direct Backend: http://localhost:5000"
    print_status "  • Via Nginx: http://localhost"
    print_status "  • Health Check: http://localhost:5000/health"
}

# Function to stop services
stop_services() {
    print_status "Stopping VersaLogIQ services..."
    docker-compose down
    print_success "VersaLogIQ services stopped"
}

# Function to restart services
restart_services() {
    print_status "Restarting VersaLogIQ services..."
    docker-compose restart
    print_success "VersaLogIQ services restarted"
}

# Function to show status
show_status() {
    print_status "VersaLogIQ service status:"
    docker-compose ps
}

# Function to show logs
show_logs() {
    if [ -n "$2" ]; then
        print_status "Showing logs for service: $2"
        docker-compose logs -f "$2"
    else
        print_status "Showing logs for all services:"
        docker-compose logs -f
    fi
}

# Function to clean everything
clean_services() {
    print_warning "This will stop all services and remove containers and volumes!"
    read -p "Are you sure? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_status "Cleaning VersaLogIQ deployment..."
        docker-compose down -v --remove-orphans
        docker system prune -f
        print_success "VersaLogIQ deployment cleaned"
    else
        print_status "Clean operation cancelled"
    fi
}

# Function to update services with enhanced build detection and verification
update_services() {
    print_status "Updating VersaLogIQ services..."
    
    # Check if we're in a git repository for change tracking
    local git_available=false
    if command -v git &> /dev/null && git rev-parse --git-dir > /dev/null 2>&1; then
        git_available=true
        local current_commit=$(git rev-parse HEAD)
        print_status "Current git commit: ${current_commit:0:8}"
    fi
    
    # Store current container IDs for comparison
    local old_backend_id=$(docker-compose ps -q versalogiq-backend 2>/dev/null || echo "")
    
    print_status "Pulling latest external images..."
    docker-compose pull
    
    print_status "Forcing rebuild of services to ensure code changes are applied..."
    # Use --no-cache to force rebuild of our custom images
    # Use --force-recreate to ensure containers are recreated even if config hasn't changed
    docker-compose build --no-cache versalogiq-backend
    
    print_status "Stopping existing services to avoid configuration conflicts..."
    docker-compose down > /dev/null 2>&1 || true
    
    print_status "Starting services with fresh containers..."
    docker-compose up -d
    
    # Wait for services to stabilize
    print_status "Waiting for services to stabilize..."
    sleep 10
    
    # Verify services are healthy
    print_status "Verifying service health..."
    local health_check_passed=true
    local max_retries=6  # 60 seconds total (6 * 10 seconds)
    local retry_count=0
    
    while [ $retry_count -lt $max_retries ]; do
        local unhealthy_services=$(docker-compose ps --format "table {{.Name}}\t{{.State}}" | grep -v "Up (healthy)" | grep -v "Name" | wc -l)
        
        if [ "$unhealthy_services" -eq 0 ]; then
            print_success "All services are healthy!"
            health_check_passed=true
            break
        else
            retry_count=$((retry_count + 1))
            print_warning "Services still starting... (attempt $retry_count/$max_retries)"
            docker-compose ps
            sleep 10
        fi
    done
    
    if [ "$health_check_passed" = false ]; then
        print_error "Some services failed health checks after update!"
        docker-compose ps
        print_error "Update may have failed. Check logs with: $0 logs"
        return 1
    fi
    
    # Test application endpoint
    print_status "Testing application endpoint..."
    local endpoint_test_passed=false
    local endpoint_retry_count=0
    local max_endpoint_retries=3
    
    while [ $endpoint_retry_count -lt $max_endpoint_retries ]; do
        if curl -f http://localhost:5000/health > /dev/null 2>&1; then
            print_success "Application endpoint is responding!"
            endpoint_test_passed=true
            break
        else
            endpoint_retry_count=$((endpoint_retry_count + 1))
            print_warning "Endpoint test failed, retrying... (attempt $endpoint_retry_count/$max_endpoint_retries)"
            sleep 5
        fi
    done
    
    if [ "$endpoint_test_passed" = false ]; then
        print_error "Application endpoint is not responding after update!"
        print_error "Check logs with: $0 logs versalogiq-backend"
        return 1
    fi
    
    # Show new container information
    local new_backend_id=$(docker-compose ps -q versalogiq-backend 2>/dev/null || echo "")
    if [ "$old_backend_id" != "$new_backend_id" ] && [ -n "$new_backend_id" ]; then
        print_success "Backend container was recreated (old: ${old_backend_id:0:12}, new: ${new_backend_id:0:12})"
    fi
    
    # Show final status
    print_status "Final service status:"
    docker-compose ps
    
    if [ "$git_available" = true ]; then
        local new_commit=$(git rev-parse HEAD)
        if [ "$current_commit" != "$new_commit" ]; then
            print_success "Git commit updated from ${current_commit:0:8} to ${new_commit:0:8}"
        else
            print_status "Git commit unchanged: ${current_commit:0:8}"
        fi
    fi
    
    print_success "VersaLogIQ services updated and verified successfully!"
    print_status "Access the application at:"
    print_status "  • Direct Backend: http://localhost:5000"
    print_status "  • Via Nginx: http://localhost"
    print_status "  • Health Check: http://localhost:5000/health"
}

# Function to check for code changes and show diff
check_changes() {
    print_status "Checking for code changes..."
    
    if ! command -v git &> /dev/null; then
        print_warning "Git not available. Cannot check for changes."
        return 1
    fi
    
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        print_warning "Not in a git repository. Cannot check for changes."
        return 1
    fi
    
    # Check if there are uncommitted changes
    if ! git diff-index --quiet HEAD --; then
        print_status "Uncommitted changes found:"
        git diff --name-status
        echo ""
        print_status "Modified files details:"
        git diff --stat
        echo ""
        print_warning "You have uncommitted changes that will be included in the build."
    else
        print_success "No uncommitted changes found."
    fi
    
    # Check recent commits
    print_status "Recent commits (last 5):"
    git log --oneline -5
    
    # Show current branch and status
    local current_branch=$(git branch --show-current 2>/dev/null || echo "unknown")
    print_status "Current branch: $current_branch"
    
    # Check if we're ahead/behind remote
    if git remote > /dev/null 2>&1; then
        local remote_branch="origin/$current_branch"
        if git rev-parse --verify "$remote_branch" > /dev/null 2>&1; then
            local ahead=$(git rev-list --count HEAD..$remote_branch 2>/dev/null || echo "0")
            local behind=$(git rev-list --count $remote_branch..HEAD 2>/dev/null || echo "0")
            
            if [ "$ahead" -gt 0 ]; then
                print_warning "Your branch is $ahead commits behind remote."
            fi
            if [ "$behind" -gt 0 ]; then
                print_status "Your branch is $behind commits ahead of remote."
            fi
            if [ "$ahead" -eq 0 ] && [ "$behind" -eq 0 ]; then
                print_success "Your branch is up to date with remote."
            fi
        fi
    fi
}

# Function to check health
check_health() {
    print_status "Checking VersaLogIQ health..."
    
    # Check if containers are running
    if docker-compose ps | grep -q "Up"; then
        print_success "Containers are running"
    else
        print_error "Some containers are not running"
        docker-compose ps
        return 1
    fi
    
    # Check backend health endpoint
    if curl -f http://localhost:5000/health > /dev/null 2>&1; then
        print_success "Backend health check passed"
    else
        print_error "Backend health check failed"
        return 1
    fi
    
    # Check if nginx is responding
    if curl -f http://localhost > /dev/null 2>&1; then
        print_success "Nginx proxy health check passed"
    else
        print_warning "Nginx proxy health check failed (this is OK if nginx service is disabled)"
    fi
    
    print_success "VersaLogIQ is healthy!"
}

# Main script logic
case "${1:-help}" in
    "start")
        start_services
        ;;
    "stop")
        stop_services
        ;;
    "restart")
        restart_services
        ;;
    "status")
        show_status
        ;;
    "logs")
        show_logs "$@"
        ;;
    "clean")
        clean_services
        ;;
    "update")
        update_services
        ;;
    "changes")
        check_changes
        ;;
    "health")
        check_health
        ;;
    "help"|*)
        show_help
        ;;
esac