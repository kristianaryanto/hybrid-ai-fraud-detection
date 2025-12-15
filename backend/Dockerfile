# Gunakan base image Python yang ramping
FROM python:3.9-slim

# Set working directory di dalam container
WORKDIR /app

# Salin file requirements dan install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Salin seluruh kode aplikasi
COPY . .

# Ekspos port yang digunakan oleh FastAPI
EXPOSE 8088

# Perintah untuk menjalankan aplikasi saat container dimulai
# Pastikan model sudah dilatih sebelum menjalankan ini
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8088"]