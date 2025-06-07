#!/bin/bash
# Simple environment setup for local development
set -e
if [ ! -f .env ]; then
    cp .env-example .env
    echo ".env created from template. Update secrets as needed."
else
    echo ".env already exists."
fi
