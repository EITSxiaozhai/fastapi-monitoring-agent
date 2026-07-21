"""认证与鉴权：管理端 JWT 登录 + 客户端 API Key 校验。"""

import hmac
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import get_settings

_bearer = HTTPBearer(auto_error=False)


def verify_credentials(username: str, password: str) -> bool:
    """校验管理员账号密码（常量时间比较，防时序攻击）。"""
    s = get_settings()
    ok_user = hmac.compare_digest(username, s.admin_username)
    ok_pass = hmac.compare_digest(password, s.admin_password)
    return ok_user and ok_pass


def create_access_token(subject: str) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=s.jwt_expire_minutes),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def decode_token(token: str) -> dict:
    s = get_settings()
    return jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])


def verify_api_key(api_key: str | None) -> bool:
    if not api_key:
        return False
    return api_key in get_settings().api_key_set


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """REST 接口的 JWT 鉴权依赖，返回用户名。"""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="未提供认证凭据"
        )
    try:
        payload = decode_token(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="无效或过期的令牌"
        ) from exc
    return payload.get("sub", "")
