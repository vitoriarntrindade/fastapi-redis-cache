"""Testes unitários para app/services.py.

Validamos o comportamento de cache hit e cache miss de forma isolada,
mockando o Redis e o cliente HTTP externo (httpx).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import fetch_exchange_rate


@pytest.fixture()
def redis_mock() -> AsyncMock:
    """Mock base do Redis para os testes de serviço."""
    return AsyncMock()


async def test_fetch_exchange_rate_cache_hit(redis_mock: AsyncMock) -> None:
    """Deve retornar o valor do cache sem chamar a API externa.

    Quando o Redis retorna um valor para a chave, o service deve
    retornar esse valor imediatamente com status 'hit'.
    """
    redis_mock.get = AsyncMock(return_value="5.20")

    rate, status = await fetch_exchange_rate(redis_mock, "USD", "BRL")

    assert rate == 5.20
    assert status == "hit"
    redis_mock.get.assert_called_once_with("exchange_rate:USD:BRL")


async def test_fetch_exchange_rate_cache_miss(redis_mock: AsyncMock) -> None:
    """Deve chamar a API externa e salvar o resultado no Redis.

    Quando o Redis não encontra a chave (retorna None), o service deve
    consultar a API externa, salvar o resultado no cache e retornar 'miss'.
    """
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.set = AsyncMock()

    fake_response = MagicMock()
    fake_response.json.return_value = {"USDBRL": {"bid": "5.35"}}
    fake_response.raise_for_status = MagicMock()

    with patch("app.services.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=fake_response)
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)

        rate, status = await fetch_exchange_rate(redis_mock, "USD", "BRL")

    assert rate == 5.35
    assert status == "miss"
    redis_mock.set.assert_called_once()


async def test_fetch_exchange_rate_salva_ttl_correto(redis_mock: AsyncMock) -> None:
    """Deve salvar o valor no Redis com o TTL configurado em Settings.

    Verifica que o argumento `ex` passado ao redis.set corresponde ao
    valor de cache_ttl_seconds definido nas configurações.
    """
    from app.config import settings

    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.set = AsyncMock()

    fake_response = MagicMock()
    fake_response.json.return_value = {"USDBRL": {"bid": "5.10"}}
    fake_response.raise_for_status = MagicMock()

    with patch("app.services.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=fake_response)
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)

        await fetch_exchange_rate(redis_mock, "USD", "BRL")

    _args, kwargs = redis_mock.set.call_args
    assert kwargs.get("ex") == settings.cache_ttl_seconds
