from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from pathlib import Path
import sys

app = FastAPI(
    title="示例 API",
    description="一个简单的 FastAPI Demo",
    version="1.0.0"
)

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


def _get_resource_dir() -> Path:
    mod = sys.modules.get(__package__ or __name__.split(".")[0])
    if mod and hasattr(mod, "_RESOURCE_DIR"):
        return Path(mod._RESOURCE_DIR)
    return Path(__file__).parent


@app.get("/config", tags=["配置"])
async def get_config():
    config_path = _get_resource_dir() / "resources" / "config.txt"
    if not config_path.exists():
        raise HTTPException(status_code=404, detail="Config file not found")
    content = config_path.read_text(encoding="utf-8")
    return {"config": content}
