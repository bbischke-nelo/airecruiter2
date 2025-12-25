#!/bin/bash
# deploy.sh - Deploy and rebuild airecruiter2 containers

set -e

echo "=== AI Recruiter v2 Deployment Script ==="
echo

# Disable buildkit for human-readable output
export DOCKER_BUILDKIT=0
export COMPOSE_DOCKER_CLI_BUILD=0

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
AIRECRUITER_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

# Change to airecruiter2 directory
cd "$AIRECRUITER_DIR"

# Check if docker-compose.yml exists
if [ ! -f "docker-compose.yml" ]; then
    echo "ERROR: docker-compose.yml not found in $AIRECRUITER_DIR!"
    exit 1
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "WARNING: .env file not found. Make sure environment variables are set."
fi

echo "Working in directory: $AIRECRUITER_DIR"

echo
echo "Step 1: Pulling latest changes from git..."
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "  Current branch: $CURRENT_BRANCH"
git pull origin "$CURRENT_BRANCH"

echo
echo "Step 2: Stopping existing containers..."
docker-compose down

echo
echo "Step 3: Pruning old images and containers..."
docker system prune -f

echo
echo "Step 4: Building containers (one at a time to avoid OOM)..."
echo "  Building airecruiter2-api..."
docker-compose build airecruiter2-api

echo "  Building airecruiter2-processor..."
docker-compose build airecruiter2-processor

echo "  Building airecruiter2-web..."
docker-compose build airecruiter2-web

echo
echo "Step 5: Starting containers..."
docker-compose up -d

echo
echo "Step 6: Waiting for services to start..."
sleep 10

echo
echo "Step 7: Checking container status..."
docker-compose ps

echo
echo "Step 8: Testing health endpoints..."
curl -s -f http://localhost:8001/health && echo " API OK" || echo " API health check failed"
curl -s -f http://localhost:3001/recruiter2/health && echo " Web OK" || echo " Web health check failed"

echo
echo "=== Deployment Complete! ==="
echo
echo "To view logs: docker-compose logs -f [service_name]"
echo "  API:       docker-compose logs -f airecruiter2-api"
echo "  Web:       docker-compose logs -f airecruiter2-web"
echo "  Processor: docker-compose logs -f airecruiter2-processor"
