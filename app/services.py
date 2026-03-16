import logging

import httpx
import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)

AWESOME_API_URL = "https://economia.awesomeapi.com.br/last/{pair}"


def _cache_key(from_currency: str, to_currency: str) -> str:
    """Gera a chave usada para armazenar a cotação no Redis.

    Args:
        from_currency: Moeda de origem (ex: USD).
        to_currency: Moeda de destino (ex: BRL).

    Returns:
        String no formato ``exchange_rate:FROM:TO``.
    """
    return f"exchange_rate:{from_currency}:{to_currency}"


async def fetch_exchange_rate(
    redis: aioredis.Redis,
    from_currency: str,
    to_currency: str,
) -> tuple[float, str]:
    """Retorna a cotação entre duas moedas e a origem do dado.

    Verifica o cache Redis antes de consultar a API externa.
    Salva o resultado no Redis com TTL se vier da API externa.

    Args:
        redis: Cliente Redis compartilhado injetado pelo lifespan.
        from_currency: Moeda de origem em caixa alta (ex: USD).
        to_currency: Moeda de destino em caixa alta (ex: BRL).

    Returns:
        Tupla ``(rate, cache_status)`` onde ``cache_status`` é ``"hit"``
        ou ``"miss"``.

    Raises:
        httpx.HTTPStatusError: Se a API externa retornar erro HTTP.
        KeyError: Se a resposta da API não contiver o par de moedas esperado.
    """
    key = _cache_key(from_currency, to_currency)

    cached = await redis.get(key)
    if cached is not None:
        logger.info("cache hit | key=%s", key)
        return float(cached), "hit"

    logger.info("cache miss | key=%s | consultando API externa", key)

    pair = f"{from_currency}-{to_currency}"
    url = AWESOME_API_URL.format(pair=pair)

    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()

    key_response = f"{from_currency}{to_currency}"
    rate = float(response.json()[key_response]["bid"])

    await redis.set(key, rate, ex=settings.cache_ttl_seconds)
    logger.info(
        "cotação salva no cache | key=%s | rate=%s | ttl=%ss",
        key,
        rate,
        settings.cache_ttl_seconds,
    )

    return rate, "miss"
