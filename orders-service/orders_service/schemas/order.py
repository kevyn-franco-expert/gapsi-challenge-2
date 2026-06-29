"""Pydantic schemas for the orders API."""
from __future__ import annotations
from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


class OrderItem(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    qty: int = Field(..., ge=1, le=999)


class OrderCreateRequest(BaseModel):
    customer_id: str = Field(..., min_length=1, max_length=255)
    items: List[OrderItem] = Field(..., min_length=1)


class OrderResponse(BaseModel):
    order_id: str
    customer_id: str
    status: str
    created_at: datetime
    items: List[OrderItem]

    model_config = {"from_attributes": True}
