#!/bin/bash
# Development environment setup script

set -e

echo "==================================="
echo "Projektant Copilot - Dev Setup"
echo "==================================="

# Check if running from project root
if [ ! -f "README.md" ]; then
    echo "Error: Please run this script from the project root directory"
    exit 1
fi

# Check prerequisites
echo "Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "Error: Docker Compose is not installed"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

echo "✓ All prerequisites met"

# Start Docker services
echo ""
echo "Starting Docker services..."
cd docker
docker-compose up -d

echo "Waiting for services to be healthy..."
sleep 10

# Check service health
docker-compose ps

cd ..

# Setup Python backend
echo ""
echo "Setting up Python backend..."
cd backend

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create .env if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file from example..."
    cp .env.example .env
    echo "⚠️  IMPORTANT: Edit backend/.env and add your API keys!"
fi

# Run migrations
echo ""
echo "Running database migrations..."
alembic upgrade head

cd ..

# Test backend
echo ""
echo "Testing backend connection..."
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

sleep 5

if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✓ Backend is running successfully"
else
    echo "✗ Backend health check failed"
fi

kill $BACKEND_PID

cd ..

echo ""
echo "==================================="
echo "Setup Complete!"
echo "==================================="
echo ""
echo "Next steps:"
echo "1. Edit backend/.env and add your API keys"
echo "2. Start backend: cd backend && source venv/bin/activate && uvicorn app.main:app --reload"
echo "3. Open http://localhost:8000/docs to see API"
echo "4. Build Revit plugin in Visual Studio"
echo ""
echo "Useful commands:"
echo "  - docker-compose logs: View service logs"
echo "  - docker-compose down: Stop all services"
echo "  - docker-compose restart: Restart services"
echo ""
