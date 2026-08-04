"""内部服务端点：仅供部署在同一内网、持有共享密钥的服务调用，不做用户鉴权。

典型调用方是 agent Node 服务。这些端点可能返回敏感信息（如明文 LLM api_key），
必须仅在内网可达，切勿暴露到公网或将返回值写入日志。
"""
import secrets

from fastapi import APIRouter, Header, HTTPException

from app.core.config import settings
from app.core.llm import get_llm_config

router = APIRouter(prefix="/internal", tags=["internal"])


@router.get("/llm-config")
async def get_internal_llm_config(x_internal_secret: str | None = Header(default=None)):
    """返回当前生效的 LLM 配置（含明文 api_key），供内网 Node 服务直接调用 LLM。

    通过 X-Internal-Secret 头与 settings.internal_api_secret 比对鉴权；
    未配置 secret 时端点关闭（403），密钥不符返回 401。
    """
    secret = (settings.internal_api_secret or "").strip()
    if not secret:
        raise HTTPException(status_code=403, detail="内部接口未启用")
    if not x_internal_secret or not secrets.compare_digest(x_internal_secret, secret):
        raise HTTPException(status_code=401, detail="无效的内部访问密钥")
    return await get_llm_config()
