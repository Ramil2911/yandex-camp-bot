FROM python:3.11-slim

WORKDIR /app

COPY security-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY common /app/common
COPY security-service /app

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
