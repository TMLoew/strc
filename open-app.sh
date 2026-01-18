#!/bin/bash

# Structured Products Analysis - Quick Open Script
# Opens the application in default browser

set -e

echo "Opening Structured Products Analysis..."
echo ""

# Check if backend is running
if curl -s http://localhost:8000/docs > /dev/null 2>&1; then
    echo "✓ Backend is running"

    # Open API docs
    echo "  Opening API docs: http://localhost:8000/docs"
    open "http://localhost:8000/docs"

    # Check if frontend is running
    if curl -s http://localhost:5173 > /dev/null 2>&1; then
        echo "✓ Frontend is running"
        echo "  Opening frontend: http://localhost:5173"
        open "http://localhost:5173"
    else
        echo "ℹ Frontend not running (start with: bash start.sh)"
    fi
else
    echo "✗ Backend is not running"
    echo ""
    echo "To start the application:"
    echo "  1. Double-click 'Structured Products.app'"
    echo "  2. OR run: bash start.sh"
    echo ""
    exit 1
fi

echo ""
echo "Done! Application opened in browser."
