"""Testes de integração para o endpoint GET /exchange-rate.

Usamos o AsyncClient com ASGITransport para simular requisições HTTP
reais sem abrir rede, com Redis e API externa completamente mockados.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient


async def test_exchange_rate_cache_hit(
    client: AsyncClient,
    mock_redis: AsyncMock,
) -> None:
    """Deve retornar 200 com cache='hit' quando o valor está no Redis."""
    mock_redis.get = AsyncMock(return_value="5.20")

    response = await client.get("/exchange-rate?from=USD&to=BRL")

    assert response.status_code == 200
    body = response.json()
    assert body["from_currency"] == "USD"
    assert body["to_currency"] == "BRL"
    assert body["rate"] == 5.20
    assert body["cache"] == "hit"


async def test_exchange_rate_cache_miss(
    client: AsyncClient,
    mock_redis: AsyncMock,
) -> None:
    """Deve retornar 200 com cache='miss' quando o valor não está no Redis."""
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock()

    fake_response = MagicMock()
    fake_response.json.return_value = {"USDBRL": {"bid": "5.50"}}
    fake_response.raise_for_status = MagicMock()

    with patch("app.services.httpx.AsyncClient") as mock_client_class:
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=fake_response)
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)

        response = await client.get("/exchange-rate?from=USD&to=BRL")

    assert response.status_code == 200
    assert response.json()["cache"] == "miss"
    assert response.json()["rate"] == 5.50


async def test_exchange_rate_moedas_em_maiusculo(
    client: AsyncClient,
    mock_redis: AsyncMock,
) -> None:
    """Deve normalizar os parâmetros para maiúsculo independente da entrada."""
    mock_redis.get = AsyncMock(return_value="5.20")

    response = await client.get("/exchange-rate?from=usd&to=brl")

    assert response.status_code == 200
    body = response.json()
    assert body["from_currency"] == "USD"
    assert body["to_currency"] == "BRL"


async def test_exchange_rate_parametros_faltando(client: AsyncClient) -> None:
    """Deve retornar 422 quando os parâmetros obrigatórios não são enviados."""
    response = await client.get("/exchange-rate")

    assert response.status_code == 422


async def test_exchange_rate_falha_api_externa(
    client: AsyncClient,
    mock_redis: AsyncMock,
) -> None:
    """Deve retornar 502 quando a API externa falha."""
    mock_redis.get = AsyncMock(return_value=None)

    with patch("app.services.httpx.AsyncClient") as mock_client_class:
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=Exception("timeout"))
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)

        response = await client.get("/exchange-rate?from=USD&to=BRL")

    assert response.status_code == 502
