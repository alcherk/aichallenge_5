#!/bin/bash
# Script to check if Chunkenizer is running and optionally start it

CHUNKENIZER_URL="${CHUNKENIZER_API_URL:-http://localhost:8000}"
CHUNKENIZER_DIR="../Chunkenizer"

echo "Checking Chunkenizer status..."

# Check if Chunkenizer is responding
if curl -s -f "${CHUNKENIZER_URL}/api/health" > /dev/null 2>&1; then
    echo "✓ Chunkenizer is running at ${CHUNKENIZER_URL}"
    curl -s "${CHUNKENIZER_URL}/api/health" | python3 -m json.tool 2>/dev/null || echo "  (Health check response received)"
    exit 0
else
    echo "✗ Chunkenizer is not running at ${CHUNKENIZER_URL}"
    
    # Check if docker-compose.yml exists
    if [ -f "${CHUNKENIZER_DIR}/docker-compose.yml" ]; then
        echo ""
        echo "To start Chunkenizer, run:"
        echo "  cd ${CHUNKENIZER_DIR}"
        echo "  docker-compose up -d"
        echo ""
        echo "Or start it now? (y/n)"
        read -r response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            cd "${CHUNKENIZER_DIR}" || exit 1
            echo "Starting Chunkenizer..."
            docker-compose up -d
            echo "Waiting for Chunkenizer to start..."
            sleep 5
            if curl -s -f "${CHUNKENIZER_URL}/api/health" > /dev/null 2>&1; then
                echo "✓ Chunkenizer started successfully!"
                curl -s "${CHUNKENIZER_URL}/api/health" | python3 -m json.tool 2>/dev/null || echo "  (Health check response received)"
            else
                echo "✗ Chunkenizer failed to start. Check logs with: docker-compose logs"
                exit 1
            fi
        fi
    else
        echo "Chunkenizer directory not found at ${CHUNKENIZER_DIR}"
        echo "Please start Chunkenizer manually or update CHUNKENIZER_API_URL"
        exit 1
    fi
fi
