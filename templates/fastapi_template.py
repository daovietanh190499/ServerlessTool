from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
import os
import json
from typing import Dict, Any, Optional
import logging

# Import script người dùng
from main import process
from utils import call_tool_api

# Thiết lập logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Khởi tạo FastAPI app
app = FastAPI(
    title=os.environ.get("TOOL_NAME", "Tool API"),
    description="API được tạo tự động từ Dashboard Quản lý Công cụ",
    version="1.0.0"
)

# Thiết lập CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Xác thực API key
API_KEY = os.environ.get("API_KEY", "")
api_key_header = APIKeyHeader(name="X-API-Key")

async def verify_api_key(api_key: str = Depends(api_key_header)):
    if API_KEY and api_key != API_KEY:
        raise HTTPException(status_code=401, detail="API key không hợp lệ")
    return api_key

@app.get("/")
async def root():
    return {"message": "Chào mừng đến với API Tool"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/process", dependencies=[Depends(verify_api_key)])
async def process_data(request: Request):
    try:
        # Đọc dữ liệu từ request
        data = await request.json()
        
        # Ghi log
        logger.info(f"Nhận request với dữ liệu: {data}")
        
        # Gọi hàm process từ script người dùng
        result = process(data)
        
        # Trả về kết quả
        return {"result": result}
    except Exception as e:
        logger.error(f"Lỗi khi xử lý request: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 