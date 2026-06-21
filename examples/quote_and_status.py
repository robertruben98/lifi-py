"""Reproduce the validated flow: a keyless cross-chain quote, then status polling.

Quotes 1 USDC from Arbitrum -> Base. The quote includes a ready-to-sign
``transactionRequest``; once you sign and broadcast it, feed the resulting tx
hash to ``poll_status`` to track the bridge to completion.

Run:  python examples/quote_and_status.py
"""

from __future__ import annotations

from lifi_py import LifiClient

# Chain ids and token addresses for the validated example.
ARBITRUM = 42161
BASE = 8453
USDC_ARBITRUM = "0xaf88d065e77c8cC2239327C5EDb3A432268e5831"
USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
WALLET = "0x47E2D28169738039755586743E2dfCF3bd643f86"


def main() -> None:
    # No API key needed — keyless quotes work out of the box.
    with LifiClient() as client:
        quote = client.get_quote(
            from_chain=ARBITRUM,
            to_chain=BASE,
            from_token=USDC_ARBITRUM,
            to_token=USDC_BASE,
            from_amount="1000000",  # 1 USDC (6 decimals)
            from_address=WALLET,
        )

        print(f"Best tool:   {quote.tool}")
        print(f"You receive: {quote.estimate.to_amount} (min {quote.estimate.to_amount_min})")
        print(f"Duration:    ~{quote.estimate.execution_duration}s")

        tx = quote.transaction_request
        assert tx is not None
        print("\nReady-to-sign transaction:")
        print(f"  to:      {tx.to}")
        print(f"  chainId: {tx.chain_id}")
        print(f"  value:   {tx.value}")
        print(f"  data:    {tx.data[:42] if tx.data else None}...")

        # For signing with web3.py (extra: pip install 'lifi-py[exec]'):
        #   web3_tx = tx.as_web3_tx()
        #   signed = account.sign_transaction(web3_tx)
        #   tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        #
        # Then track the bridge until it completes on the destination chain:
        #   final = client.poll_status(tx_hash=tx_hash.hex(), bridge=quote.tool)
        #   print(final.status)  # DONE / FAILED

        if client.rate_limit is not None:
            print(
                f"\nRate limit: {client.rate_limit.remaining}/{client.rate_limit.limit} "
                f"remaining (resets in {client.rate_limit.reset}s)"
            )


if __name__ == "__main__":
    main()
