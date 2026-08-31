# 1. Base Python Image
FROM python:3.11-slim

# 2. Environment Variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8 \
    PORT=8000

# 3. System Dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 4. Work Directory
WORKDIR /app

# 5. Install Python Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 6. Copy Application Source Code
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY run_server.py .

# 7. Expose Port
EXPOSE 8000

# 8. Run Server
CMD ["python", "run_server.py"]
