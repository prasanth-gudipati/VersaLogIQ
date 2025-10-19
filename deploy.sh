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
    echo "  update      Pull latest images and restart"
    echo "  health      Check application health"
    echo "  help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 start              # Start VersaLogIQ"
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

# Function to update services
update_services() {
    print_status "Updating VersaLogIQ services..."
    docker-compose pull
    docker-compose up -d --build
    print_success "VersaLogIQ services updated"
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
    "health")
        check_health
        ;;
    "help"|*)
        show_help
        ;;
esac