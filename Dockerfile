FROM python:3.12-slim AS fastapi

WORKDIR /app

ENV PYTHONPATH=/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

WORKDIR /app/apps/backend

ARG APP_PORT=8080

ENV APP_PORT=$APP_PORT

EXPOSE $APP_PORT

CMD ["sh", "-c", "python -m uvicorn main:app --host 0.0.0.0 --port $APP_PORT"]
