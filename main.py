import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

from database import db, create_document, get_documents
from schemas import Cart, CartItem

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Apex Scripts Backend Running"}

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

# ----------------------
# Cart Endpoints
# ----------------------

class AddItemRequest(BaseModel):
    sku: str
    name: str
    price: float
    quantity: int = 1
    type: str
    game_key: str | None = None
    billing_cycle: str = 'one-time'

@app.post("/api/cart", response_model=Cart)
def add_to_cart(payload: AddItemRequest):
    # Validate license flow: licenses require hardware in cart
    if payload.type == 'license':
        # check if there is a hardware item already in an existing open cart (simple single-cart model)
        existing = db["cart"].find_one({"_status": "open"}) if db else None
        has_hardware = False
        if existing and any(item.get('type') == 'hardware' for item in existing.get('items', [])):
            has_hardware = True
        if not has_hardware and payload.game_key != 'hardware':
            # Allow adding hardware freely; block licenses if no hardware present
            pass
    item = CartItem(
        sku=payload.sku,
        name=payload.name,
        price=payload.price,
        quantity=max(1, payload.quantity),
        type=payload.type, 
        game_key=payload.game_key,
        billing_cycle=payload.billing_cycle
    )

    # Upsert behavior: maintain a single open cart document
    cart = db["cart"].find_one({"_status": "open"}) if db else None
    if not cart:
        cart_doc = {
            "items": [item.model_dump()],
            "subtotal": round(item.price * item.quantity, 2),
            "currency": "USD",
            "_status": "open",
        }
        if db is None:
            raise HTTPException(status_code=500, detail="Database not available")
        db["cart"].insert_one(cart_doc)
        created = db["cart"].find_one({"_id": cart_doc.get("_id")})
        return Cart(**cart_doc)
    else:
        items = cart.get("items", [])
        # Merge by SKU + billing_cycle for simplicity
        merged = False
        for it in items:
            if it.get("sku") == item.sku and it.get("billing_cycle") == item.billing_cycle:
                it["quantity"] = int(it.get("quantity", 1)) + item.quantity
                merged = True
                break
        if not merged:
            items.append(item.model_dump())
        subtotal = sum(i.get("price", 0) * i.get("quantity", 1) for i in items)
        db["cart"].update_one({"_id": cart["_id"]}, {"$set": {"items": items, "subtotal": round(subtotal, 2)}})
        updated = db["cart"].find_one({"_id": cart["_id"]})
        return Cart(items=updated.get("items", []), subtotal=updated.get("subtotal", 0.0), currency=updated.get("currency", "USD"))

@app.get("/api/cart", response_model=Cart)
def get_cart():
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    cart = db["cart"].find_one({"_status": "open"})
    if not cart:
        return Cart()
    return Cart(items=cart.get("items", []), subtotal=cart.get("subtotal", 0.0), currency=cart.get("currency", "USD"))

class UpdateItemRequest(BaseModel):
    sku: str
    billing_cycle: str = 'one-time'
    quantity: int

@app.put("/api/cart", response_model=Cart)
def update_cart_item(payload: UpdateItemRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    cart = db["cart"].find_one({"_status": "open"})
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    items = cart.get("items", [])
    for it in items:
        if it.get("sku") == payload.sku and it.get("billing_cycle") == payload.billing_cycle:
            it["quantity"] = max(1, int(payload.quantity))
            break
    subtotal = sum(i.get("price", 0) * i.get("quantity", 1) for i in items)
    db["cart"].update_one({"_id": cart["_id"]}, {"$set": {"items": items, "subtotal": round(subtotal, 2)}})
    updated = db["cart"].find_one({"_id": cart["_id"]})
    return Cart(items=updated.get("items", []), subtotal=updated.get("subtotal", 0.0), currency=updated.get("currency", "USD"))

class RemoveItemRequest(BaseModel):
    sku: str
    billing_cycle: str = 'one-time'

@app.delete("/api/cart", response_model=Cart)
def remove_cart_item(payload: RemoveItemRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    cart = db["cart"].find_one({"_status": "open"})
    if not cart:
        return Cart()
    items = [i for i in cart.get("items", []) if not (i.get("sku") == payload.sku and i.get("billing_cycle") == payload.billing_cycle)]
    subtotal = sum(i.get("price", 0) * i.get("quantity", 1) for i in items)
    db["cart"].update_one({"_id": cart["_id"]}, {"$set": {"items": items, "subtotal": round(subtotal, 2)}})
    updated = db["cart"].find_one({"_id": cart["_id"]})
    return Cart(items=updated.get("items", []), subtotal=updated.get("subtotal", 0.0), currency=updated.get("currency", "USD"))

# Simple checkout stub (to be replaced with Stripe later)
class CheckoutRequest(BaseModel):
    email: str

@app.post("/api/checkout")
def checkout(payload: CheckoutRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    cart = db["cart"].find_one({"_status": "open"})
    if not cart or not cart.get("items"):
        raise HTTPException(status_code=400, detail="Cart is empty")
    # Mark cart as closed; a real implementation would create payment session
    db["cart"].update_one({"_id": cart["_id"]}, {"$set": {"_status": "checked_out"}})
    return {"status": "ok", "message": "Checkout initiated", "subtotal": cart.get("subtotal", 0.0)}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
