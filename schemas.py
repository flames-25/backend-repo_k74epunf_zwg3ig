from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List

# Collection: product
class Product(BaseModel):
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in dollars")
    category: str = Field(..., description="Product category")
    in_stock: bool = Field(True, description="Whether product is in stock")
    image_url: Optional[str] = Field(None, description="Image URL")

# Collection: order
class OrderItem(BaseModel):
    product_id: str
    quantity: int = Field(..., gt=0)

class Customer(BaseModel):
    name: str
    email: EmailStr
    address: str

class Order(BaseModel):
    customer: Customer
    items: List[OrderItem]
    total: Optional[float] = Field(None, ge=0)
    currency: str = "USD"
