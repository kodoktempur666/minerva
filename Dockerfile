FROM python:3.11-slim

# Environment variables:
# - PYTHONDONTWRITEBYTECODE: Mencegah Python membuat file .pyc
# - PYTHONUNBUFFERED: Memastikan output log langsung muncul secara real-time
# - TZ: Sinkronisasi waktu log dengan WIB / Asia/Jakarta
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Jakarta

WORKDIR /app

# Install tzdata untuk zona waktu
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Salin dependencies dan install terlebih dahulu untuk optimasi Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Salin seluruh kode program
COPY . .

# Menggunakan SIGINT agar bot dapat berhenti secara aman (graceful shutdown) saat di-stop
STOPSIGNAL SIGINT

# Perintah menjalankan bot
CMD ["python", "bot.py"]
