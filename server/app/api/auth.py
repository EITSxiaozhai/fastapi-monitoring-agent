"""管理端登录鉴权接口（Ant Design Pro 约定）。"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..config import get_settings
from ..security import create_access_token, get_current_user, verify_credentials

router = APIRouter(prefix="/api/v1", tags=["auth"])


class LoginParams(BaseModel):
    username: str
    password: str
    type: str = "account"


class LoginResult(BaseModel):
    status: str
    type: str
    currentAuthority: str = "guest"
    token: str | None = None


@router.post("/login/account", response_model=LoginResult)
async def login(params: LoginParams) -> LoginResult:
    if verify_credentials(params.username, params.password):
        token = create_access_token(params.username)
        return LoginResult(
            status="ok", type=params.type, currentAuthority="admin", token=token
        )
    return LoginResult(status="error", type=params.type, currentAuthority="guest")


@router.get("/currentUser")
async def current_user(user: str = Depends(get_current_user)) -> dict:
    return {
        "success": True,
        "data": {
            "name": user,
            "userid": user,
            "access": "admin",
            "avatar": "https://gw.alipayobjects.com/zos/antfincdn/XAosXuNZyF/BiazfanxmamNRoxxVxka.png",
        },
    }


@router.post("/login/outLogin")
async def logout() -> dict:
    return {"data": {}, "success": True}


@router.get("/config/public")
async def public_config() -> dict:
    """供前端展示的非敏感配置。"""
    s = get_settings()
    return {"offline_threshold_seconds": s.offline_threshold_seconds}
