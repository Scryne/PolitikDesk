FROM python:3.12-slim

# B-54: worker imajı `embed-local` ekstrasıyla kurulur (torch + sentence-
# transformers), API/beat imajı kurulmaz. Aksi halde her konteyner ~2,5 GB
# taşır. Boş bırakılırsa temel kurulum yapılır.
ARG PD_EXTRAS=""

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/opt/hf-cache

WORKDIR /app

# Bağımlılık katmanı önce — kod değişince yeniden kurulmasın
COPY pyproject.toml README.md ./
COPY politikdesk/__init__.py ./politikdesk/__init__.py
# torch varsayılan PyPI'da CUDA tekerleriyle gelir (~2,5 GB fazladan). MVP tek
# VPS üzerinde CPU ile koşar (D12), bu yüzden CPU indeksinden kurulur.
RUN pip install --upgrade pip \
 && if [ -n "$PD_EXTRAS" ]; then \
        pip install --index-url https://download.pytorch.org/whl/cpu torch \
     && pip install -e ".[$PD_EXTRAS]"; \
    else \
        pip install -e .; \
    fi

COPY politikdesk ./politikdesk
COPY migrations ./migrations
COPY scripts ./scripts
COPY config ./config

EXPOSE 8000

CMD ["uvicorn", "politikdesk.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
