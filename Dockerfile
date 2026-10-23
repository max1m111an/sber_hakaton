FROM python:3.12-slim AS fastapi

WORKDIR /app

ENV PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/opt/hf \
    ML_ENCODER=cointegrated/rubert-tiny2 \
    ML_ARTIFACT_DIR=/app/ml_artifacts

# torch — CPU-сборка (~200 МБ вместо ~2,5 ГБ с CUDA). Для GPU:
#   docker compose build --build-arg TORCH_INDEX=https://download.pytorch.org/whl/cu121
ARG TORCH_INDEX=https://download.pytorch.org/whl/cpu
RUN pip install --index-url ${TORCH_INDEX} torch

COPY requirements.txt .
RUN pip install -r requirements.txt

# Модель эмбеддингов скачивается при сборке и лежит в образе (HF_HOME):
# в рантайме сеть до HuggingFace не нужна — подходит для закрытого контура
RUN python -c "import os; from sentence_transformers import SentenceTransformer; SentenceTransformer(os.environ['ML_ENCODER'])"
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

COPY . .

WORKDIR /app/apps/backend

ARG APP_PORT=8080

ENV APP_PORT=$APP_PORT

EXPOSE $APP_PORT

CMD ["sh", "-c", "python -m uvicorn main:app --host 0.0.0.0 --port $APP_PORT"]
