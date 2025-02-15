# inference.Dockerfile
FROM python:3.9-slim

RUN apt-get update && apt-get install -y libpq-dev gcc git

WORKDIR /app

# Set env variables for DB or MLflow if needed
ENV TIMESCALEDB_HOST=timescaledb
ENV POSTGRES_PORT=5432
ENV POSTGRES_DB=postgres
ENV POSTGRES_USER=postgres
ENV POSTGRES_PASSWORD=postgresso
ENV MLFLOW_TRACKING_URI=http://mlflow:5000

# Install dependencies
COPY requirements-forecasting.txt .
RUN pip install --no-cache-dir -r requirements-forecasting.txt

# Copy your entire backend code
COPY . /app

# The command now runs the inference pipeline
CMD ["python", "inference_pipeline.py"]
