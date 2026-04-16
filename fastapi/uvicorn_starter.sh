#!/bin/sh
# Ensure Python uses the correct path
export PATH="/usr/local/bin:$PATH"

# Debug: Verify if Python sees Alembic and Uvicorn
python3 -m alembic -h >/dev/null 2>&1 || { echo "Error: alembic not found"; exit 1; }
python3 -m uvicorn --help >/dev/null 2>&1 || { echo "Error: uvicorn not found"; exit 1; }

if [ "$APP_ENV" = "development" ]; then

    # Check if we are using Supabase (skip local DB wait)
    if [ "$USE_SUPABASE" != "true" ]; then
        echo -n "Waiting for the DBMS to accept connection "
        while [ 1 ]; do
            if nc -vz db "$DATABASE_PORT"; then
                break
            fi
            echo -n "."
            sleep 1
        done
        echo ""
    else
        echo "Using Supabase - Skipping local DB wait..."
    fi

    echo "Running database migrations..."
    python3 -m alembic upgrade head  # Run Alembic migrations
    echo "Migrations applied"

    if [ "$DEBUG" = "1" ]; then
        echo "Running FastAPI in Development Mode (with auto-reload)"
        python3 -m uvicorn main:fastapi_app --host 0.0.0.0 --port 8080 --reload  # Runs like Flask dev server
    else
        echo "Starting FastAPI in development mode with Gunicorn (managing Uvicorn workers)"
        python3 -m gunicorn -c "$PWD"/gunicorn.config.py main:fastapi_app
    fi
else
    echo "Starting FastAPI in production mode with Gunicorn"
    python3 -m gunicorn -c "$PWD"/gunicorn.config.py main:fastapi_app
fi
exec "$@"
