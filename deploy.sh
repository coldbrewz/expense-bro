#!/bin/bash

echo "🚀 Starting deployment to Oracle VM..."

# 1. Copy local project files to Oracle VM home directory
echo "📤 Uploading files via SCP..."
MSYS_NO_PATHCONV=1 scp -o ServerAliveInterval=60 -q -r -i /tmp/oracle.key /d/Users/muhammad.najih/Documents/expense-bro/ ubuntu@129.225.9.167:~/

# 2. SSH into VM, enter folder, and rebuild Docker containers
echo "🔄 Rebuilding Docker containers on server..."
ssh -o ServerAliveInterval=60 -i /tmp/oracle.key ubuntu@129.225.9.167 "cd ~/expense-bro && docker compose up -d --build"

echo "✅ Deployment completed successfully!"
