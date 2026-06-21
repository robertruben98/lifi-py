# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2026-06-21

### Changed
- Documentation enrichment pass: rich Google-style docstrings (Args/Returns/
  Raises, with examples on `get_quote` and `poll_status`) across the sync and
  async clients, `Field(description=...)` on every response model, documented
  `Status.is_done`/`is_failed`/`is_terminal` and the exception hierarchy.
- Added `CHANGELOG.md`, `CONTRIBUTING.md` and README status badges (CI, PyPI,
  Python versions, license).

## [0.1.0] - 2026-06-21

### Added
- Initial release: a typed Python client for the LI.FI API (bridge + DEX
  aggregator for any-to-any cross-chain swaps).
- Synchronous `LifiClient` and asynchronous `AsyncLifiClient` over `httpx`.
- Pydantic v2 response models with full type hints; `py.typed` packaged.
- Endpoints: `get_quote`, `get_status`, `get_routes`, `get_step_transaction`,
  `get_chains`, `get_tokens`, `get_tools`, `get_connections`.
- `poll_status()` helper that polls until the transfer reaches a terminal state.
- Rate-limit awareness: reads the `ratelimit-*` response headers, throttles
  proactively when the quota is exhausted, and retries `429`s with backoff.
- Optional `[exec]` extra (`web3.py`) with `TransactionRequest.as_web3_tx()`.
- Configurable `api_key`, `api_key_header` and `base_url`.

[0.1.1]: https://github.com/robertruben98/lifi-py/releases/tag/v0.1.1
[0.1.0]: https://github.com/robertruben98/lifi-py/releases/tag/v0.1.0
