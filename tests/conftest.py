"""Fixtures compartilhadas entre todos os testes.

Aqui configuramos o cliente HTTP de teste (AsyncClient) com mocks
para Redis e API externa, garantindo que os testes sejam isolados,
rápidos e sem dependências de infraestrutura real.
"""

from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.dependencies import check_rate_limit, get_redis
from app.main import app


@pytest.fixture()
def mock_redis() -> AsyncMock:
    """Retorna um mock completo do cliente Redis.

    O pipeline é configurado com um MagicMock síncrono (não AsyncMock),
    pois redis.pipeline() é um método síncrono que retorna um context manager
    assíncrono. O execute() interno é async.
    """
    redis = AsyncMock()

    pipeline = MagicMock()
    pipeline.__aenter__ = AsyncMock(return_value=pipeline)
    pipeline.__aexit__ = AsyncMock(return_value=False)
    pipeline.incr = MagicMock(return_value=pipeline)
    pipeline.ttl = MagicMock(return_value=pipeline)
    pipeline.execute = AsyncMock(return_value=[1, -1])

    redis.pipeline = MagicMock(return_value=pipeline)
    redis.expire = AsyncMock()

    return redis


@pytest.fixture()
def test_app(mock_redis: AsyncMock) -> Generator[FastAPI, None, None]:
    """Retorna a aplicação FastAPI com as dependências Redis substituídas pelo mock.

    Sobrescrevemos tanto `get_redis` quanto `check_rate_limit` para que o
    `app.state.redis` (populado pelo lifespan, que não executa em testes) não
    seja necessário, mantendo os testes de rota totalmente isolados.
    """

    async def _noop_rate_limit() -> None:
        pass

    app.dependency_overrides[get_redis] = lambda: mock_redis
    app.dependency_overrides[check_rate_limit] = _noop_rate_limit
    yield app
    app.dependency_overrides.clear()


@pytest.fixture()
async def client(test_app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Retorna um AsyncClient configurado para testar a aplicação via ASGI.

    Usa ASGITransport para chamar a aplicação diretamente em memória,
    sem abrir sockets de rede reais.
    """
    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test",
    ) as ac:
        yield ac
