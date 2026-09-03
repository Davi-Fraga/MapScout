# Build stage / Runtime usando Python 3.12 e uv
FROM python:3.12-slim

# Evita criação de arquivos .pyc e força saída não bufferizada
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Instala ferramentas básicas e uv
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Instala uv para gerenciamento ultra-rápido de pacotes
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copia arquivos de dependência
COPY pyproject.toml /app/

# Instala dependências do projeto
RUN uv pip install --system --no-cache -e .

# Copia o código-fonte e os templates
COPY src/ /app/src/

# Porta padrão de execução (o Render injeta $PORT)
ENV PORT=8000
EXPOSE 8000

# Executa o servidor uvicorn vinculado a 0.0.0.0 e à porta dinâmica do Render
CMD ["sh", "-c", "python -m uvicorn mapscout.web.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
