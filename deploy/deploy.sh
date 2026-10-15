#!/bin/bash

# Production Deployment Script for Tenable SERM
# Usage: ./deploy.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_ROOT="$DEPLOY_DIR"
DEPLOY_DIR="$PROJECT_ROOT/deploy"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Tenable SERM Production Deployment${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Step 1: Pull latest code
echo -e "${YELLOW}[1/5] Pulling latest code from repository...${NC}"
cd "$PROJECT_ROOT"
git pull origin main || git pull origin master
echo -e "${GREEN}✓ Code updated${NC}"
echo ""

# Step 2: Build frontend
echo -e "${YELLOW}[2/5] Building frontend...${NC}"
cd "$PROJECT_ROOT/frontend"
npm ci
npm run build
echo -e "${GREEN}✓ Frontend built successfully${NC}"
echo ""

# Step 3: Build backend Docker images
echo -e "${YELLOW}[3/5] Building Docker images...${NC}"
cd "$PROJECT_ROOT"
docker compose -f "$DEPLOY_DIR/docker-compose.prod.yml" build
echo -e "${GREEN}✓ Docker images built${NC}"
echo ""

# Step 4: Stop old containers
echo -e "${YELLOW}[4/5] Stopping old containers...${NC}"
cd "$DEPLOY_DIR"
docker compose -f docker-compose.prod.yml down
echo -e "${GREEN}✓ Old containers stopped${NC}"
echo ""

# Step 5: Start new containers
echo -e "${YELLOW}[5/5] Starting new containers...${NC}"
docker compose -f docker-compose.prod.yml up -d
echo -e "${GREEN}✓ Containers started${NC}"
echo ""

# Wait for health checks
echo -e "${YELLOW}Waiting for services to be healthy...${NC}"
sleep 30

# Check service status
echo -e "${YELLOW}Checking service status...${NC}"
docker compose -f docker-compose.prod.yml ps

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment completed successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Services:"
echo "  - Frontend: http://localhost"
echo "  - API: http://localhost/api/"
echo ""
echo "To view logs:"
echo "  cd $DEPLOY_DIR"
echo "  docker compose -f docker-compose.prod.yml logs -f"
echo ""
