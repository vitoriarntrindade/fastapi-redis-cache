import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import FastAPI

from app.config import settings
from app.routes import router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Gerencia o ciclo de vida da aplicação.

    Cria um ConnectionPool Redis compartilhado na inicialização e o fecha
    corretamente no encerramento. Isso garante reuso eficiente de conexões
    em toda a aplicação sem criar conexões avulsas por requisição.
    """
    pool = aioredis.ConnectionPool.from_url(
        f"redis://{settings.redis_host}:{settings.redis_port}",
        decode_responses=True,
    )
    app.state.redis = aioredis.Redis(connection_pool=pool)
    logger.info(
        "redis connection pool criado | host=%s | port=%d",
        settings.redis_host,
        settings.redis_port,
    )

    yield

    await app.state.redis.aclose()
    logger.info("redis connection pool encerrado")


app = FastAPI(
    title="Exchange Rate API",
    description="Cotação de moedas com cache Redis",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router)
