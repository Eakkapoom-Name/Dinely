#!/bin/sh

if [ "$APP_ENV" = "development" ]; then
    npm install --verbose
    npm run dev
    exec "$@"
elif [ "$APP_ENV" = "production" ]; then
    npm run build
fi
