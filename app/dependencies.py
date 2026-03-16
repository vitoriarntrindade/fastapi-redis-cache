import logging

import redis.asyncio as aioredis
from fastapi import HTTPException, Request, status

from app.config import settings

logger = logging.getLogger(__name__)


async def get_redis(request: Request) -> aioredis.Redis:
    """Retorna o cliente Redis compartilhado criado no lifespan da aplicação.

    Args:
        request: Objeto de requisição FastAPI que carrega o app.state.

    Returns:
        Instância de aioredis.Redis com pool de conexão compartilhado.
    """
    return request.app.state.redis  # type: ignore[no-any-return]


async def check_rate_limit(request: Request) -> None:
    """Verifica se o IP do cliente excedeu o limite de requisições configurado.

    Utiliza um mecanismo de janela fixa (fixed window) com Redis e chaves TTL.
    Em caso de falha no Redis, adota estratégia fail-open para não derrubar a API.

    Args:
        request: Objeto de requisição FastAPI com metadados do cliente.

    Raises:
        HTTPException: 429 se o limite de requisições for excedido.
    """
    client_ip = request.client.host if request.client else "unknown"
    key = f"rate_limit:{client_ip}"
    redis = await get_redis(request)

    try:
        async with redis.pipeline() as pipe:
            pipe.incr(key)
            pipe.ttl(key)
            results = await pipe.execute()

        requests_count: int = results[0]
        ttl: int = results[1]

        # Define expiração apenas na primeira requisição da janela
        if requests_count == 1:
            await redis.expire(key, settings.rate_limit_window)

        if requests_count > settings.rate_limit_requests:
            retry_after = ttl if ttl > 0 else settings.rate_limit_window
            logger.warning(
                "rate limit excedido | ip=%s | requests=%d/%d | retry_after=%ds",
                client_ip,
                requests_count,
                settings.rate_limit_requests,
                retry_after,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit excedido. Tente novamente em {retry_after}s.",
            )

    except aioredis.RedisError:
        logger.exception("falha ao consultar Redis para rate limit | ip=%s", client_ip)
