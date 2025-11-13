import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Any
from datetime import datetime

from database import db, create_document, get_documents
from bson import ObjectId

app = FastAPI(title="Ecommerce API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Helpers ----------

def doc_to_dict(doc: dict) -> dict:
    out = {}
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            out[k] = str(v)
        elif isinstance(v, datetime):
            out[k] = v.isoformat()
        else:
            out[k] = v
    if "_id" in out:
        out["id"] = out.pop("_id")
    return out


# ---------- Schemas ----------

class ProductIn(BaseModel):
    title: str
    description: Optional[str] = None
    price: float = Field(..., ge=0)
    category: str
    in_stock: bool = True
    image_url: Optional[str] = None

class ProductOut(ProductIn):
    id: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class OrderItem(BaseModel):
    product_id: str
    quantity: int = Field(..., gt=0)

class CustomerInfo(BaseModel):
    name: str
    email: EmailStr
    address: str

class OrderIn(BaseModel):
    customer: CustomerInfo
    items: List[OrderItem]

class OrderOut(BaseModel):
    id: str
    total: float
    currency: str = "USD"
    created_at: Optional[str] = None


# ---------- Basic Routes ----------

@app.get("/")
def read_root():
    return {"message": "Ecommerce Backend Running"}

@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


# ---------- Product Routes ----------

@app.get("/api/products", response_model=List[ProductOut])
def list_products(category: Optional[str] = None) -> Any:
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    query = {"category": category} if category else {}
    docs = get_documents("product", query)
    return [ProductOut(**doc_to_dict(d)) for d in docs]

@app.post("/api/products", response_model=dict)
def create_product(product: ProductIn):
    try:
        new_id = create_document("product", product)
        return {"id": new_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/products/{product_id}", response_model=ProductOut)
def get_product(product_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        doc = db["product"].find_one({"_id": ObjectId(product_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid product id")
    if not doc:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductOut(**doc_to_dict(doc))


# ---------- Order Routes ----------

@app.post("/api/orders", response_model=OrderOut)
def create_order(order: OrderIn):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    # Compute total on server using current product prices
    total = 0.0
    for item in order.items:
        try:
            prod = db["product"].find_one({"_id": ObjectId(item.product_id)})
        except Exception:
            raise HTTPException(status_code=400, detail=f"Invalid product id: {item.product_id}")
        if not prod:
            raise HTTPException(status_code=404, detail=f"Product not found: {item.product_id}")
        price = float(prod.get("price", 0))
        total += price * item.quantity

    order_doc = {
        "customer": order.customer.model_dump(),
        "items": [i.model_dump() for i in order.items],
        "total": round(total, 2),
        "currency": "USD",
    }

    try:
        new_id = create_document("order", order_doc)
        # Fetch back for timestamps
        saved = db["order"].find_one({"_id": ObjectId(new_id)})
        saved_dict = doc_to_dict(saved)
        return OrderOut(id=saved_dict["id"], total=saved_dict["total"], currency=saved_dict.get("currency", "USD"), created_at=saved_dict.get("created_at"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/orders", response_model=List[OrderOut])
def list_orders(limit: int = 50):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    docs = db["order"].find().sort("created_at", -1).limit(limit)
    out: List[OrderOut] = []
    for d in docs:
        dd = doc_to_dict(d)
        out.append(OrderOut(id=dd["id"], total=dd.get("total", 0.0), currency=dd.get("currency", "USD"), created_at=dd.get("created_at")))
    return out


# ---------- Diagnostics ----------

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
