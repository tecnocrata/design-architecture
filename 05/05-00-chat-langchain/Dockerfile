# filepath: /workspaces/design-architecture/05/03-dockerize/Dockerfile
# ------------------- Stage 0: Base Stage ------------------------------
FROM python:3.11-alpine AS base

# Set the working directory in the container
WORKDIR /app

# Install tini, a tiny init for containers, and other build dependencies
# tini is used to properly handle signals and reap zombie processes
RUN apk add --no-cache tini gcc musl-dev python3-dev libffi-dev openssl-dev cargo pkgconfig

# ------------------- Stage 1: Build Stage ------------------------------
# This stage is used to build Python dependencies
FROM base AS builder

# Copy only the requirements file to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
# Using --no-cache-dir to reduce image size
# Using --prefix /install to install packages in a specific directory
# that can be easily copied to the final stage.
RUN pip install --no-cache-dir --prefix="/install" -r requirements.txt

# Copy the rest of the application source code
COPY . .

# ------------------- Stage 2: Final Stage ------------------------------
# This is the final image that will be deployed
FROM base AS final

# Create a non-root user and group for security
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

# Copy installed Python packages from the builder stage
COPY --from=builder /install /usr/local

# Copy the application code from the builder stage
# Ensure the appuser owns these files
COPY --from=builder --chown=appuser:appgroup /app /app

# Set the user to the non-root user
USER appuser

# Expose the port the app runs on
EXPOSE 50505

# Use tini as the entrypoint to manage the Gunicorn process
ENTRYPOINT ["/sbin/tini", "--"]

# Command to run the application using Gunicorn
# Assumes gunicorn.conf.py is in the WORKDIR (/app)
# And that your Quart app instance or factory is accessible as "src.myapp:create_app()"
# The gunicorn.conf.py should handle adding 'src' to sys.path
CMD ["gunicorn", "--config", "gunicorn.conf.py", "src.myapp:create_app()"]
