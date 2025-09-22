FROM python:3.11-slim

WORKDIR /app

COPY dashboard-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY common /app/common
COPY dashboard-service /app

EXPOSE $PORT

CMD streamlit run app/dashboard.py --server.port $PORT --server.address 0.0.0.0 --server.headless true
