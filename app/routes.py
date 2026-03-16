import logging

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.dependencies import check_rate_limit, get_redis
from app.services import fetch_exchange_rate

logger = logging.getLogger(__name__)

router = APIRouter()


class ExchangeRateResponse(BaseModel):
    """Modelo da resposta do endpoint de cotação."""

    from_currency: str
    to_currency: str
    rate: float
    cache: str


@router.get(
    "/exchange-rate",
    response_model=ExchangeRateResponse,
    dependencies=[Depends(check_rate_limit)],
    summary="Retorna a cotação entre duas moedas",
)
async def get_exchange_rate(
    from_currency: str = Query(alias="from"),
    to_currency: str = Query(alias="to"),
    redis: aioredis.Redis = Depends(get_redis),
) -> ExchangeRateResponse:
    """Retorna a cotação de câmbio entre duas moedas.

    - **from**: moeda de origem (ex: USD)
    - **to**: moeda de destino (ex: BRL)
    """
    try:
        rate, cache_status = await fetch_exchange_rate(
            redis,
            from_currency.upper(),
            to_currency.upper(),
        )
    except Exception:
        logger.exception(
            "falha ao obter cotação | from=%s | to=%s",
            from_currency,
            to_currency,
        )
        raise HTTPException(
            status_code=502,
            detail="Erro ao consultar a API externa de cotação.",
        )

    return ExchangeRateResponse(
        from_currency=from_currency.upper(),
        to_currency=to_currency.upper(),
        rate=rate,
        cache=cache_status,
    )
