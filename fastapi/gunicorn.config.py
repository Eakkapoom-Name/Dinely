# Change directory to the FastAPI app directory before loading
chdir = '/fastapi_app'

# The number of worker processes for handling requests.
workers = 2

# The number of worker threads for handling requests.
threads = 2

# The socket to bind.
bind = ['0.0.0.0:8080']

# How verbose the Gunicorn error logs should be.
loglevel = 'debug'

# Capture stdout and stderr in logs.
capture_output = True

# Enable hot reload for development.
reload = True

# Use Uvicorn workers to serve FastAPI.
worker_class = 'uvicorn.workers.UvicornWorker'
