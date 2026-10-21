FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY deploy/russian_trusted_root_ca.pem /usr/local/share/ca-certificates/russian_trusted_root_ca.crt
RUN update-ca-certificates

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY assets ./assets
COPY deploy/russian_trusted_root_ca.pem ./deploy/russian_trusted_root_ca.pem

ENV MAX_ROOT_CA_PATH=/app/deploy/russian_trusted_root_ca.pem
ENV STORAGE_PATH=/app/data
ENV PYTHONUNBUFFERED=1

RUN mkdir -p /app/data

EXPOSE 8080

CMD ["python", "-m", "app.main", "--mode", "polling"]
