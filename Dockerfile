FROM python:3.11-slim
WORKDIR /app

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser && chown -R appuser:appuser /app
USER appuser

# Install deps first for better caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY src/ ./src/
RUN mkdir -p /app/data

EXPOSE 8080
ENV DEDUP_DB_PATH=/app/data/dedup.db
CMD ["python", "-m", "src.main"]
