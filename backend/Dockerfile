FROM python:3.11-slim

WORKDIR /app

# Copy backend requirements and source
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/main.py ./main.py

# Copy frontend static files into the image so FastAPI can serve them
COPY frontend ./frontend

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]