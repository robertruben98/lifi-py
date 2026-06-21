"""Async variant: fetch a keyless cross-chain quote with AsyncLifiClient.

Run:  python examples/async_quote.py
"""

from __future__ import annotations

import asyncio

from lifi_py import AsyncLifiClient


async def main() -> None:
    async with AsyncLifiClient() as client:
        quote = await client.get_quote(
            from_chain=42161,  # Arbitrum
            to_chain=8453,  # Base
            from_token="0xaf88d065e77c8cC2239327C5EDb3A432268e5831",  # USDC
            to_token="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",  # USDC
            from_amount="1000000",
            from_address="0x47E2D28169738039755586743E2dfCF3bd643f86",
        )
        print(f"{quote.tool}: receive {quote.estimate.to_amount} USDC on Base")
        assert quote.transaction_request is not None
        print(f"tx to: {quote.transaction_request.to}")


if __name__ == "__main__":
    asyncio.run(main())
