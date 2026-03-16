# 💱 Exchange Rate API

> API de cotação de moedas em tempo real com cache Redis, rate limiting e pipeline de CI completo.

[![CI](https://github.com/vitoriarntrindade/fastapi-redis-cache/actions/workflows/ci.yml/badge.svg)](https://github.com/vitoriarntrindade/fastapi-redis-cache/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.135-009688?logo=fastapi)
![Redis](https://img.shields.io/badge/Redis-7-red?logo=redis)
![Ruff](https://img.shields.io/badge/lint-ruff-purple)
![MyPy](https://img.shields.io/badge/types-mypy-blue)

---

## O que este projeto resolve

APIs que consultam serviços externos enfrentam dois problemas clássicos em produção:

**1. Latência e custo por requisição**
Cada chamada à AwesomeAPI leva ~200–500ms e pode ser cobrada por volume. Se 1.000 usuários consultam `USD → BRL` ao mesmo tempo, são 1.000 chamadas desnecessárias para um dado que não muda em segundos.

**2. Abuso e instabilidade**
Sem proteção, um único cliente mal-intencionado (ou um loop de código) pode saturar sua API e derrubar o serviço para todos.

Este projeto resolve ambos com **Redis**, de duas formas distintas:

---

## Como o Redis foi usado

### 1. Cache com TTL — evitar chamadas repetidas à API externa

```
Cliente → FastAPI → Redis (hit?) ──→ resposta em < 1ms
                         │
                     (miss)
                         ↓
                   AwesomeAPI (~300ms) → salva no Redis → resposta
```

Ao receber uma requisição de cotação, a API verifica primeiro o Redis.
Se a chave existir (**cache hit**), o valor é retornado imediatamente sem tocar a rede externa.
Se não existir (**cache miss**), a API consulta a AwesomeAPI, salva o resultado com um TTL de 60 segundos e retorna o valor.

O campo `"cache"` na resposta deixa explícito ao cliente de onde o dado veio:

```json
{
  "from_currency": "USD",
  "to_currency": "BRL",
  "rate": 5.23,
  "cache": "hit"
}
```

### 2. Rate Limiting com Fixed Window — proteger contra abuso

```
Cliente A → INCR rate_limit:192.168.1.1 → 7  → OK
Cliente A → INCR rate_limit:192.168.1.1 → 11 → 429 Too Many Requests
```

A cada requisição, um contador por IP é incrementado no Redis com `INCR`.
Na primeira requisição da janela, uma expiração de 60 segundos é definida com `EXPIRE`.
Quando o contador ultrapassa o limite configurado, a API retorna `429` com o tempo restante para retry.

Essa operação usa **pipeline Redis** (`INCR` + `TTL` em bloco atômico) para minimizar round-trips.

### Por que um ConnectionPool compartilhado?

Em vez de abrir uma conexão nova por requisição (caro, lento, esgota o pool do Redis), a aplicação cria um único `ConnectionPool` no startup via `lifespan` do FastAPI e o disponibiliza via `app.state`. Todas as dependências (`get_redis`) consomem o mesmo pool, que só é fechado no shutdown.

---

## Arquitetura

```
fastapi-redis-cache/
├── app/
│   ├── main.py           # FastAPI app + lifespan (ConnectionPool Redis)
│   ├── routes.py         # Endpoint GET /exchange-rate
│   ├── services.py       # Lógica de cache + chamada à AwesomeAPI
│   ├── dependencies.py   # get_redis + check_rate_limit (FastAPI Depends)
│   ├── config.py         # Settings via pydantic-settings + .env
│   └── logging_config.py # dictConfig centralizado (sem prints espalhados)
├── tests/
│   ├── conftest.py       # Fixtures: mock_redis, test_app, client
│   ├── test_services.py  # Testes unitários do service (cache hit/miss/TTL)
│   ├── test_routes.py    # Testes do endpoint HTTP (200, 422, 502)
│   └── test_rate_limit.py# Testes do rate limiter (expire, limite, 429)
├── .github/workflows/
│   └── ci.yml            # Pipeline: lint → typecheck → test
├── Dockerfile            # Multi-stage build, usuário não-root
├── docker-compose.yml    # API + Redis com healthcheck
└── pyproject.toml        # Dependências, Ruff, MyPy, Pytest config
```

---

## Stack e decisões técnicas

| Tecnologia | Papel | Por quê |
|---|---|---|
| **FastAPI** | Framework web | Performance async nativa, Swagger automático, Dependency Injection elegante |
| **Redis (asyncio)** | Cache + Rate Limiting | Sub-milissegundo, TTL nativo, pipeline atômico |
| **httpx** | Cliente HTTP | Async-first, interface limpa, testável com mocks |
| **pydantic-settings** | Configurações | Leitura de `.env` com validação de tipos automática |
| **uv** | Gerenciador de pacotes | 10–100x mais rápido que pip, lockfile determinístico |
| **Ruff** | Lint + Format | Substitui flake8 + isort + black em um único binário ultrarrápido |
| **MyPy** | Tipagem estática | Detecta erros de tipo antes de chegar em produção |
| **pytest-asyncio** | Testes async | Suíte de testes completa sem subir infraestrutura real |
| **Docker** | Containerização | Multi-stage build, imagem mínima, usuário não-root |

---

## Qualidade de código

Este projeto trata qualidade como não negociável:

- **Tipagem estática completa** — todas as funções têm assinaturas tipadas. `mypy` não reporta nenhum erro.
- **PEP 8 + imports organizados** — `ruff check` e `ruff format` garantem estilo consistente com limite de 88 caracteres.
- **Zero `print()`** — logs estruturados via `logging.dictConfig`, com nível, módulo e timestamp em cada linha.
- **11 testes cobrindo as 3 camadas** — service, endpoint HTTP e rate limiter, todos isolados com mocks sem dependência de infraestrutura real.
- **Docstrings no estilo Google** — todas as funções públicas documentadas com `Args`, `Returns` e `Raises`.

---

## Pré-requisitos

- [Docker](https://docs.docker.com/get-docker/) + [Docker Compose](https://docs.docker.com/compose/)
- **OU** Python 3.12+ e [uv](https://docs.astral.sh/uv/getting-started/installation/) para rodar localmente

---

## Como rodar

### Com Docker (recomendado — Linux e Windows)

```bash
# Subir API + Redis
docker compose up --build

# Em background
docker compose up --build -d

# Ver logs
docker compose logs -f api

# Derrubar
docker compose down
```

A API estará disponível em `http://localhost:8000`.

---

### Localmente sem Docker

**Linux / macOS**
```bash
# Instalar uv (caso não tenha)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clonar e entrar no projeto
git clone https://github.com/vitoriarntrindade/fastapi-redis-cache.git
cd fastapi-redis-cache

# Instalar dependências
uv sync

# Configurar variáveis (copie e edite conforme necessário)
cp .env.example .env

# Subir apenas o Redis via Docker
docker run -d -p 6379:6379 redis:7-alpine

# Rodar a API
uv run python run.py
```

**Windows (PowerShell)**
```powershell
# Instalar uv
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Clonar e entrar no projeto
git clone https://github.com/vitoriarntrindade/fastapi-redis-cache.git
cd fastapi-redis-cache

# Instalar dependências
uv sync

# Subir apenas o Redis via Docker
docker run -d -p 6379:6379 redis:7-alpine

# Rodar a API
uv run python run.py
```

---

## Variáveis de ambiente

Crie um arquivo `.env` na raiz do projeto (opcional — todos têm valores padrão):

```env
REDIS_HOST=localhost
REDIS_PORT=6379
CACHE_TTL_SECONDS=60
RATE_LIMIT_REQUESTS=10
RATE_LIMIT_WINDOW=60
```

---

## Endpoints

### `GET /exchange-rate`

Retorna a cotação entre duas moedas com indicação de origem do dado.

**Parâmetros:**

| Nome | Tipo | Descrição |
|---|---|---|
| `from` | `string` | Moeda de origem (ex: `USD`) |
| `to` | `string` | Moeda de destino (ex: `BRL`) |

**Exemplo de requisição:**
```bash
curl "http://localhost:8000/exchange-rate?from=USD&to=BRL"
```

**Resposta `200 OK`:**
```json
{
  "from_currency": "USD",
  "to_currency": "BRL",
  "rate": 5.23,
  "cache": "hit"
}
```

**Respostas de erro:**

| Status | Motivo |
|---|---|
| `422` | Parâmetros ausentes ou inválidos |
| `429` | Rate limit excedido — `detail` informa o tempo de espera |
| `502` | Falha ao consultar a API externa de cotação |

**Documentação interativa** (Swagger): `http://localhost:8000/docs`

---

## Testando o rate limit

Faça 12 requisições em sequência (limite padrão: 10 por minuto):

**Linux / macOS:**
```bash
for i in {1..12}; do
  curl -s -o /dev/null -w "%{http_code}\n" \
    "http://localhost:8000/exchange-rate?from=USD&to=BRL"
done
```

**Windows (PowerShell):**
```powershell
1..12 | ForEach-Object {
  Invoke-WebRequest -Uri "http://localhost:8000/exchange-rate?from=USD&to=BRL" `
    -UseBasicParsing -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty StatusCode
}
```

As primeiras 10 retornam `200`, as seguintes `429`.

---

## Rodando os testes

```bash
uv run pytest -v
```

**Saída esperada:**
```
tests/test_rate_limit.py::test_rate_limit_primeira_requisicao_define_ttl    PASSED
tests/test_rate_limit.py::test_rate_limit_dentro_do_limite_nao_lanca_excecao PASSED
tests/test_rate_limit.py::test_rate_limit_excedido_lanca_http_429            PASSED
tests/test_routes.py::test_exchange_rate_cache_hit                           PASSED
tests/test_routes.py::test_exchange_rate_cache_miss                          PASSED
tests/test_routes.py::test_exchange_rate_moedas_em_maiusculo                 PASSED
tests/test_routes.py::test_exchange_rate_parametros_faltando                 PASSED
tests/test_routes.py::test_exchange_rate_falha_api_externa                   PASSED
tests/test_services.py::test_fetch_exchange_rate_cache_hit                   PASSED
tests/test_services.py::test_fetch_exchange_rate_cache_miss                  PASSED
tests/test_services.py::test_fetch_exchange_rate_salva_ttl_correto           PASSED

11 passed in 0.20s
```

---

## Verificando qualidade do código

```bash
# Lint e formatação
uv run ruff check app/ tests/
uv run ruff format --check app/ tests/

# Tipagem estática
uv run mypy app/ tests/
```

---

## CI/CD

O pipeline do GitHub Actions executa automaticamente em todo push e pull request para `main`:

```
push → main
   │
   ├─ Lint (Ruff)       — estilo, imports, formatação
   ├─ Typecheck (MyPy)  — tipagem estática
   └─ Test (Pytest)     ← só roda se lint e typecheck passarem
        └─ Redis 7 (service container)
```

Configurações de segurança aplicadas:
- `permissions: contents: read` — menor privilégio no token do runner
- `concurrency` com `cancel-in-progress` — cancela runs antigas em pushes rápidos
- `timeout-minutes: 10` — impede runners presos

---

