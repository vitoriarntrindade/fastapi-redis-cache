"""Testes unitários para o mecanismo de Rate Limiting em app/dependencies.py.

Validamos os cenários de primeira requisição (setup do TTL), requisição
dentro do limite e requisição acima do limite (429).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.config import settings
from app.dependencies import check_rate_limit


def _make_request(redis_mock: AsyncMock, ip: str = "127.0.0.1") -> MagicMock:
    """Cria um objeto Request falso com IP e app.state.redis configurados."""
    request = MagicMock()
    request.client.host = ip
    request.app.state.redis = redis_mock
    return request


def _setup_pipeline(redis_mock: AsyncMock, count: int, ttl: int = 50) -> None:
    """Configura o mock de pipeline com retornos de INCR e TTL.

    redis.pipeline() é síncrono e retorna um context manager assíncrono,
    por isso usamos MagicMock (não AsyncMock) para o pipeline em si.
    """
    pipeline = MagicMock()
    pipeline.__aenter__ = AsyncMock(return_value=pipeline)
    pipeline.__aexit__ = AsyncMock(return_value=False)
    pipeline.incr = MagicMock(return_value=pipeline)
    pipeline.ttl = MagicMock(return_value=pipeline)
    pipeline.execute = AsyncMock(return_value=[count, ttl])
    redis_mock.pipeline = MagicMock(return_value=pipeline)


async def test_rate_limit_primeira_requisicao_define_ttl() -> None:
    """Deve chamar redis.expire na primeira requisição da janela (count == 1)."""
    redis_mock = AsyncMock()
    _setup_pipeline(redis_mock, count=1, ttl=-1)
    redis_mock.expire = AsyncMock()

    request = _make_request(redis_mock)
    await check_rate_limit(request)

    redis_mock.expire.assert_called_once_with(
        "rate_limit:127.0.0.1",
        settings.rate_limit_window,
    )


async def test_rate_limit_dentro_do_limite_nao_lanca_excecao() -> None:
    """Não deve lançar exceção quando o número de requests está dentro do limite."""
    redis_mock = AsyncMock()
    _setup_pipeline(redis_mock, count=settings.rate_limit_requests, ttl=30)
    redis_mock.expire = AsyncMock()

    request = _make_request(redis_mock)
    await check_rate_limit(request)  # não deve lançar


async def test_rate_limit_excedido_lanca_http_429() -> None:
    """Deve lançar HTTPException 429 quando o limite de requests é ultrapassado."""
    redis_mock = AsyncMock()
    _setup_pipeline(redis_mock, count=settings.rate_limit_requests + 1, ttl=45)
    redis_mock.expire = AsyncMock()

    request = _make_request(redis_mock)

    with pytest.raises(HTTPException) as exc_info:
        await check_rate_limit(request)

    assert exc_info.value.status_code == 429
    assert "45s" in exc_info.value.detail
