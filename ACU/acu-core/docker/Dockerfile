FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency profiles
COPY requirements.txt .
COPY requirements/ ./requirements/

# Install Python dependencies. Override with:
# docker build --build-arg REQUIREMENTS_FILE=requirements/vector.txt ...
ARG REQUIREMENTS_FILE=requirements/observability.txt
RUN pip install --no-cache-dir -r ${REQUIREMENTS_FILE}

# Copy application code
COPY . .

# Create logs directory and user
RUN mkdir -p logs data/vectors && \
    useradd -m -r -s /bin/bash appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Environment
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO
ENV PATH="/home/appuser/.local/bin:${PATH}"

# Health check for the FastAPI runtime.
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=5).raise_for_status()" || exit 1

# Run API/dashboard by default. CLI mode remains available with: python main.py
CMD ["python", "-m", "uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
