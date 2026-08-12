FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Bağımlılık katmanı önce — kod değişince yeniden kurulmasın
COPY pyproject.toml README.md ./
COPY politikdesk/__init__.py ./politikdesk/__init__.py
RUN pip install --upgrade pip && pip install -e .

COPY politikdesk ./politikdesk
COPY migrations ./migrations
COPY scripts ./scripts
COPY config ./config

EXPOSE 8000

CMD ["uvicorn", "politikdesk.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
