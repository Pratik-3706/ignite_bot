import base64
import aiohttp
from typing import Optional, Dict, Any

async def download_image_as_data_url(url: str, max_bytes: int = 8 * 1024 * 1024) -> Optional[str]:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    return None
                
                content_type = resp.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
                data = await resp.read()
                
                if len(data) > max_bytes:
                    return None
                
                b64 = base64.b64encode(data).decode("utf-8")
                return f"data:{content_type};base64,{b64}"
    except Exception:
        return None

def build_vision_user_message(text_prompt: str, image_url_or_data: str) -> Dict[str, Any]:
    return {
        "role": "user",
        "content": [
            {"type": "text", "text": text_prompt},
            {"type": "image_url", "image_url": {"url": image_url_or_data}}
        ]
    }
