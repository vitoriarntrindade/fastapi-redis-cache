FROM python:3.12-slim

# instala o uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# copia apenas os arquivos de dependências primeiro
# (essa layer só é reconstruída se pyproject.toml ou uv.lock mudarem)
COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev

# copia o código da aplicação
COPY app/ ./app/
COPY run.py ./

# usuário não-root por segurança
RUN useradd --no-create-home appuser
USER appuser

# desativa o buffer do Python no Docker para os logs saírem em tempo real
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD [".venv/bin/python", "run.py"]

