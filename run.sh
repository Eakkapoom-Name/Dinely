#!/bin/sh

# Check if USE_SUPABASE is set to true in .env
USE_SUPABASE=$(grep -E "^USE_SUPABASE=true" .env 2>/dev/null || echo "")

if [ -n "$USE_SUPABASE" ]; then
    echo "USE_SUPABASE=true detected, starting WITHOUT local Postgres..."
    docker compose build
    # docker compose --compatibility up -d
    docker compose up -d
else
    echo "Starting WITH local Postgres database..."
    docker compose --profile with-db build
    # docker compose --profile with-db --compatibility up -d
    docker compose --profile with-db up -d
fi
