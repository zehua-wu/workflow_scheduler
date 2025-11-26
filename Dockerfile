FROM python:3.9-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libopenslide0 \
    libgl1 \
    libglib2.0-0 \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY app/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt --timeout 1000

COPY . .

RUN mkdir -p outputs data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]