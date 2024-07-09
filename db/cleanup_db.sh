#!/bin/bash

echo "Stopping and removing Docker containers..."
docker-compose down -v

echo "Removing pgdata directory..."
rm -rf pgdata

echo "Cleanup complete."