FROM python:3.11-slim

WORKDIR /app

COPY monitoring-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY common /app/common
COPY monitoring-service /app

EXPOSE 8004 8501

# Создаем скрипт запуска
RUN echo '#!/bin/bash\n\
uvicorn app.main:app --host 0.0.0.0 --port 8004 &\n\
streamlit run app/dashboard.py --server.port 8501 --server.address 0.0.0.0 --server.headless true &\n\
wait' > /app/start.sh && chmod +x /app/start.sh

CMD ["/app/start.sh"]
