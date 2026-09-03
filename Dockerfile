# Build stage / Runtime usando Python 3.12 e uv
FROM python:3.12-slim

# Garante que o Python encontre o pacote mapscout em /app/src
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# Instala ferramentas básicas e uv
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Instala uv para gerenciamento ultra-rápido de pacotes
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copia dependências e código-fonte
COPY pyproject.toml /app/
COPY src/ /app/src/

# Instala dependências do projeto no Python do sistema
RUN uv pip install --system --no-cache -e .

# Porta padrão de execução (o Render injeta $PORT)
ENV PORT=8000
EXPOSE 8000

# Executa o servidor uvicorn vinculado a 0.0.0.0 e à porta dinâmica do Render
CMD ["sh", "-c", "python -m uvicorn mapscout.web.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
