import os
import requests
import json
from typing import Dict, Any, Optional
import logging

# Thiết lập logging
logger = logging.getLogger(__name__)

def call_tool_api(tool_slug: str, data: Dict[str, Any], timeout: int = 30) -> Optional[Dict[str, Any]]:
    """
    Gọi API của một công cụ khác
    
    Args:
        tool_slug: Slug của công cụ cần gọi
        data: Dữ liệu gửi đến API
        timeout: Thời gian chờ tối đa (giây)
        
    Returns:
        Kết quả từ API hoặc None nếu có lỗi
    """
    try:
        # Lấy API key từ biến môi trường
        api_key = os.environ.get("API_KEY", "")
        
        # Xây dựng URL
        base_url = f"http://{tool_slug}/process"
        
        # Gọi API
        headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
        response = requests.post(base_url, json=data, headers=headers, timeout=timeout)
        
        # Kiểm tra kết quả
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Lỗi khi gọi API {tool_slug}: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"Lỗi khi gọi API {tool_slug}: {str(e)}")
        return None 