import sys
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

app = FastAPI(title="示例 API", description="一个简单的 FastAPI Demo", version="1.0.0")

fake_items_db = [
    {"item_id": 1, "name": "Foo", "price": 35.4, "description": "A very nice item"},
    {"item_id": 2, "name": "Bar", "price": 12.1, "description": "Another nice item"},
    {"item_id": 3, "name": "Baz", "price": 89.0, "description": "A great item"}
]

class Item(BaseModel):
    name: str
    price: float
    description: Optional[str] = None
    tax: Optional[float] = None

class User(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None

@app.get("/", tags=["根路径"])
async def read_root():
    return {"message": "欢迎使用 FastAPI Demo!", "timestamp": datetime.now().isoformat()}

@app.get("/items/", tags=["物品"], response_model=List[dict])
async def read_items(skip: int = 0, limit: int = 10):
    return fake_items_db[skip : skip + limit]

@app.get("/items/{item_id}", tags=["物品"], response_model=dict)
async def read_item(item_id: int, q: Optional[str] = None):
    item = next((item for item in fake_items_db if item["item_id"] == item_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    if q:
        item["q"] = q
    return item

@app.post("/items/", tags=["物品"], response_model=dict, status_code=201)
async def create_item(item: Item):
    new_item = item.dict()
    new_item["item_id"] = len(fake_items_db) + 1
    fake_items_db.append(new_item)
    return new_item

@app.put("/items/{item_id}", tags=["物品"], response_model=dict)
async def update_item(item_id: int, item: Item):
    idx = next((i for i, item_db in enumerate(fake_items_db) if item_db["item_id"] == item_id), None)
    if idx is None:
        raise HTTPException(status_code=404, detail="Item not found")
    fake_items_db[idx] = {"item_id": item_id, **item.dict()}
    return fake_items_db[idx]

@app.delete("/items/{item_id}", tags=["物品"])
async def delete_item(item_id: int):
    global fake_items_db
    idx = next((i for i, item_db in enumerate(fake_items_db) if item_db["item_id"] == item_id), None)
    if idx is None:
        raise HTTPException(status_code=404, detail="Item not found")
    deleted = fake_items_db.pop(idx)
    return {"message": "Item deleted", "item": deleted}

@app.get("/health", tags=["健康检查"])
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        uvicorn.run(app=app, host="0.0.0.0", port=8000)
    else:
        print("FastAPI Demo 应用")
        print("用法: python -m weather run")
        print("然后访问: http://localhost:8000")
        print("API文档: http://localhost:8000/docs")

if __name__ == "__main__":
    main()
