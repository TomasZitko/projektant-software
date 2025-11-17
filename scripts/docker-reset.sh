#!/bin/bash
# Reset Docker environment (clean restart)

set -e

echo "Stopping all containers..."
cd docker
docker-compose down -v

echo "Removing volumes..."
docker volume prune -f

echo "Starting fresh containers..."
docker-compose up -d

echo "Waiting for services to start..."
sleep 15

echo "Checking service health..."
docker-compose ps

echo ""
echo "Docker environment reset complete!"
echo "Note: All data has been deleted. You'll need to run migrations again."
