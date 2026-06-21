# lifi-py

A typed Python client for the [LI.FI API](https://docs.li.fi/api-reference/introduction)
— the bridge + DEX aggregator for **any-to-any cross-chain** swaps and bridges
across 74 chains.

The killer feature: `get_quote()` returns a **ready-to-sign `transactionRequest`**
directly — one call, no separate assemble step.

- Sync (`LifiClient`) and async (`AsyncLifiClient`) clients on top of `httpx`.
- All responses parsed into `pydantic` v2 models with full type hints (`py.typed`).
- Built-in rate-limit awareness: reads the `ratelimit-*` headers, throttles
  proactively, and retries `429`s with backoff.
- Optional `web3.py` integration for signing/sending the returned transaction.

## Install

```bash
pip install lifi-py
# with web3 signing helpers:
pip install 'lifi-py[exec]'
```

## Quickstart — cross-chain quote with a ready-to-sign tx (keyless, <5 lines)

```python
from lifi_py import LifiClient

quote = LifiClient().get_quote(
    from_chain=42161, to_chain=8453,                                  # Arbitrum -> Base
    from_token="0xaf88d065e77c8cC2239327C5EDb3A432268e5831",          # USDC (Arbitrum)
    to_token="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",            # USDC (Base)
    from_amount="1000000", from_address="0x47E2D28169738039755586743E2dfCF3bd643f86",
)
print(quote.estimate.to_amount, quote.transaction_request.to)  # ~995000, 0x1231DEB6...
```

`quote.transaction_request` is an EVM transaction ready to sign and broadcast.

## Signing & sending (optional, `[exec]` extra)

```python
tx = quote.transaction_request.as_web3_tx()   # hex fields decoded to ints, web3-shaped
signed = account.sign_transaction({**tx, "nonce": w3.eth.get_transaction_count(account.address)})
tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
```

## Tracking a bridge to completion

```python
client = LifiClient()
status = client.poll_status(tx_hash="0x...", bridge=quote.tool)  # polls until DONE/FAILED
print(status.status, status.is_done)
```

`get_status()` does a single check; `poll_status()` polls with exponential backoff
until the transfer reaches a terminal state (or raises `TimeoutError`).

## Async

```python
import asyncio
from lifi_py import AsyncLifiClient

async def main():
    async with AsyncLifiClient() as client:
        quote = await client.get_quote(...)

asyncio.run(main())
```

## Endpoints

| Method | API endpoint |
| --- | --- |
| `get_quote(...)` | `GET /quote` — best single-step route + `transactionRequest` |
| `get_status(...)` / `poll_status(...)` | `GET /status` — track a transfer |
| `get_routes(...)` | `POST /advanced/routes` — multiple candidate routes |
| `get_step_transaction(step)` | `POST /advanced/stepTransaction` — calldata for one step |
| `get_chains()` | `GET /chains` |
| `get_tokens()` | `GET /tokens` |
| `get_tools()` | `GET /tools` — bridges + exchanges |
| `get_connections(...)` | `GET /connections` |

## Authentication & rate limits

An API key is **optional** — every endpoint above works keyless. A key only raises
your rate limits:

```python
client = LifiClient(api_key="your-key")                 # sent as `x-lifi-api-key`
client = LifiClient(api_key="k", api_key_header="x-custom-key")  # configurable header
client = LifiClient(base_url="https://staging.li.quest/v1")      # configurable base URL
```

The client reads the API's `ratelimit-limit` / `ratelimit-remaining` / `ratelimit-reset`
response headers (exposed via `client.rate_limit`). When the quota is exhausted it
pauses before the next request; on a `429` it retries with backoff respecting the
reset window, raising `LifiRateLimitError` once retries are exhausted.

## Configuration

| Argument | Default | Description |
| --- | --- | --- |
| `api_key` | `None` | Optional; raises rate limits. |
| `base_url` | `https://li.quest/v1` | API base URL. |
| `api_key_header` | `x-lifi-api-key` | Header name for the key. |
| `timeout` | `30.0` | Per-request timeout (seconds). |
| `max_retries` | `3` | Max `429` retries before raising. |
| `http_client` | `None` | Inject your own `httpx.Client` / `AsyncClient`. |

## Development

```bash
pip install -e '.[dev,exec]'
ruff check .
mypy
pytest                 # unit tests (mocked HTTP, no network)
pytest -m integration  # live smoke tests against the keyless API
```

## License

MIT
