"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal

# ----------------------
# Core domain schemas
# ----------------------

class CartItem(BaseModel):
    sku: str = Field(..., description="Unique SKU for product or license")
    name: str = Field(..., description="Display name")
    price: float = Field(..., ge=0, description="Unit price in USD")
    quantity: int = Field(1, ge=1, le=99)
    type: Literal['hardware', 'license'] = Field(...)
    game_key: Optional[str] = Field(None, description="Game identifier for license items (e.g., csgo, overwatch, r6, vmp)")
    billing_cycle: Literal['one-time', 'weekly', 'monthly'] = Field('one-time')

class Cart(BaseModel):
    items: List[CartItem] = Field(default_factory=list)
    subtotal: float = 0.0
    currency: str = 'USD'

# Example additional schemas (unused directly but kept for reference)
class User(BaseModel):
    name: str
    email: str
    address: str
    age: Optional[int] = None
    is_active: bool = True

class Product(BaseModel):
    title: str
    description: Optional[str] = None
    price: float
    category: str
    in_stock: bool = True
