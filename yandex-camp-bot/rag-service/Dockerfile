FROM python:3.11-slim

WORKDIR /app

COPY rag-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY common /app/common
COPY rag-service /app

# Создаем директорию для данных
RUN mkdir -p /app/data /app/chroma_db

EXPOSE $PORT

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port $PORT"]
