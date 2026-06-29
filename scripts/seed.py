#!/usr/bin/env python3
"""Seed script: creates a sample order against a running orders-service."""
from __future__ import annotations

import os
import sys
import uuid

import httpx

ORDERS_URL = os.getenv("ORDERS_URL", "http://localhost:8000")


def main() -> int:
    payload = {
        "customer_id": "seed-customer",
        "items": [
            {"name": "espresso", "qty": 1},
            {"name": "croissant", "qty": 2},
        ],
    }
    headers = {
        "Content-Type": "application/json",
        "Idempotency-Key": f"seed-{uuid.uuid4()}",
    }
    response = httpx.post(f"{ORDERS_URL}/orders", json=payload, headers=headers)
    print(response.status_code, response.text)
    return 0 if response.status_code in (200, 201) else 1


if __name__ == "__main__":
    sys.exit(main())
