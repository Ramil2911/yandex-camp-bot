FROM python:3.11-slim

WORKDIR /app

COPY api-gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY common /app/common
COPY api-gateway /app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
