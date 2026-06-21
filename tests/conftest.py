"""Shared fixtures: realistic LI.FI API response payloads (captured from live calls)."""

from __future__ import annotations

from typing import Any

import pytest

# A real /quote response shape (1 USDC Arbitrum -> Base via `across`), trimmed.
QUOTE_RESPONSE: dict[str, Any] = {
    "type": "lifi",
    "id": "0x123abc",
    "tool": "across",
    "toolDetails": {
        "key": "across",
        "name": "Across",
        "logoURI": "https://example.com/across.png",
    },
    "action": {
        "fromChainId": 42161,
        "toChainId": 8453,
        "fromToken": {
            "address": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
            "chainId": 42161,
            "symbol": "USDC",
            "decimals": 6,
            "name": "USD Coin",
        },
        "toToken": {
            "address": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            "chainId": 8453,
            "symbol": "USDC",
            "decimals": 6,
            "name": "USD Coin",
        },
        "fromAmount": "1000000",
        "fromAddress": "0x47E2D28169738039755586743E2dfCF3bd643f86",
        "slippage": 0.005,
    },
    "estimate": {
        "tool": "across",
        "fromAmount": "1000000",
        "toAmount": "995000",
        "toAmountMin": "990025",
        "approvalAddress": "0xaaaaa",
        "executionDuration": 24.0,
        "gasCosts": [
            {
                "type": "SEND",
                "amount": "12345",
                "token": {
                    "address": "0x0000000000000000000000000000000000000000",
                    "chainId": 42161,
                    "symbol": "ETH",
                    "decimals": 18,
                    "name": "Ether",
                },
            }
        ],
        "feeCosts": [
            {
                "name": "LP Fee",
                "amount": "5000",
                "percentage": "0.005",
                "token": {
                    "address": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
                    "chainId": 42161,
                    "symbol": "USDC",
                    "decimals": 6,
                    "name": "USD Coin",
                },
            }
        ],
    },
    "includedSteps": [
        {
            "id": "step-1",
            "type": "cross",
            "tool": "across",
            "action": {"fromChainId": 42161, "toChainId": 8453},
        }
    ],
    "integrator": "lifi-py",
    "transactionRequest": {
        "to": "0x1231DEB6f5749EF6cE6943a275A1D3E7486F4EaE",
        "data": "0xdeadbeef",
        "value": "0x0",
        "gasLimit": "0x7a120",
        "gasPrice": "0x5f5e100",
        "chainId": 42161,
    },
    "transactionId": "0xtxid",
}

STATUS_RESPONSE: dict[str, Any] = {
    "transactionId": "0xtxid",
    "sending": {
        "txHash": "0xsendhash",
        "chainId": 42161,
        "amount": "1000000",
    },
    "receiving": {
        "txHash": "0xrecvhash",
        "chainId": 8453,
        "amount": "995000",
    },
    "tool": "across",
    "status": "DONE",
    "substatus": "COMPLETED",
    "substatusMessage": "The transfer is complete.",
}

CHAINS_RESPONSE: dict[str, Any] = {
    "chains": [
        {
            "key": "eth",
            "name": "Ethereum",
            "chainType": "EVM",
            "id": 1,
            "nativeToken": {
                "address": "0x0000000000000000000000000000000000000000",
                "chainId": 1,
                "symbol": "ETH",
                "decimals": 18,
                "name": "Ether",
            },
        },
        {
            "key": "arb",
            "name": "Arbitrum",
            "chainType": "EVM",
            "id": 42161,
            "nativeToken": {
                "address": "0x0000000000000000000000000000000000000000",
                "chainId": 42161,
                "symbol": "ETH",
                "decimals": 18,
                "name": "Ether",
            },
        },
    ]
}

TOKENS_RESPONSE: dict[str, Any] = {
    "tokens": {
        "1": [
            {
                "address": "0x0000000000000000000000000000000000000000",
                "chainId": 1,
                "symbol": "ETH",
                "decimals": 18,
                "name": "Ether",
            }
        ],
        "42161": [
            {
                "address": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
                "chainId": 42161,
                "symbol": "USDC",
                "decimals": 6,
                "name": "USD Coin",
            }
        ],
    }
}

TOOLS_RESPONSE: dict[str, Any] = {
    "bridges": [
        {"key": "across", "name": "Across", "logoURI": "https://example.com/a.png"},
        {"key": "hop", "name": "Hop", "logoURI": "https://example.com/h.png"},
    ],
    "exchanges": [
        {"key": "1inch", "name": "1inch", "logoURI": "https://example.com/1.png"},
    ],
}

CONNECTIONS_RESPONSE: dict[str, Any] = {
    "connections": [
        {
            "fromChainId": 42161,
            "toChainId": 8453,
            "fromTokens": [
                {
                    "address": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
                    "chainId": 42161,
                    "symbol": "USDC",
                    "decimals": 6,
                    "name": "USD Coin",
                }
            ],
            "toTokens": [
                {
                    "address": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
                    "chainId": 8453,
                    "symbol": "USDC",
                    "decimals": 6,
                    "name": "USD Coin",
                }
            ],
        }
    ]
}

ROUTES_RESPONSE: dict[str, Any] = {
    "routes": [
        {
            "id": "route-1",
            "fromChainId": 42161,
            "toChainId": 8453,
            "fromAmount": "1000000",
            "toAmount": "995000",
            "toAmountMin": "990025",
            "fromToken": {
                "address": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
                "chainId": 42161,
                "symbol": "USDC",
                "decimals": 6,
                "name": "USD Coin",
            },
            "toToken": {
                "address": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
                "chainId": 8453,
                "symbol": "USDC",
                "decimals": 6,
                "name": "USD Coin",
            },
            "steps": [
                {
                    "id": "step-1",
                    "type": "cross",
                    "tool": "across",
                    "action": {"fromChainId": 42161, "toChainId": 8453},
                }
            ],
        }
    ]
}

STEP_TX_RESPONSE: dict[str, Any] = {
    "id": "step-1",
    "type": "cross",
    "tool": "across",
    "action": {"fromChainId": 42161, "toChainId": 8453},
    "transactionRequest": {
        "to": "0x1231DEB6f5749EF6cE6943a275A1D3E7486F4EaE",
        "data": "0xstepdata",
        "value": "0x0",
        "chainId": 42161,
    },
}


@pytest.fixture
def quote_response() -> dict[str, Any]:
    return QUOTE_RESPONSE


@pytest.fixture
def status_response() -> dict[str, Any]:
    return STATUS_RESPONSE
