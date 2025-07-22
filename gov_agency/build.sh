#!/usr/bin/env bash
# exit on error
set -o errexit

# Install Python dependencies
pip install -r requirements.txt

# Build the frontend assets
npm install
npm run build

# Run Django's collectstatic command
python manage.py collectstatic --no-input