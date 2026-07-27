"""用户机器监控页显示偏好（需登录）。"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import session_dependency
from ..models import UserMachinesDisplayPrefs
from ..schemas import MachinesDisplayPrefs, MachinesDisplayPrefsIn
from ..security import get_current_user

router = APIRouter(
    prefix="/api/v1",
    tags=["machines-display-prefs"],
    dependencies=[Depends(get_current_user)],
)

_DEFAULT = MachinesDisplayPrefs(
    show_stat_cards=True, show_machine_cards=True, hidden_agent_ids=[]
)


@router.get("/machines-display-prefs", response_model=MachinesDisplayPrefs)
async def get_machines_display_prefs(
    user: str = Depends(get_current_user),
    session: AsyncSession = Depends(session_dependency),
) -> MachinesDisplayPrefs:
    prefs = await session.get(UserMachinesDisplayPrefs, user)
    if prefs is None:
        return _DEFAULT
    return MachinesDisplayPrefs.model_validate(prefs)


@router.put("/machines-display-prefs", response_model=MachinesDisplayPrefs)
async def update_machines_display_prefs(
    body: MachinesDisplayPrefsIn,
    user: str = Depends(get_current_user),
    session: AsyncSession = Depends(session_dependency),
) -> MachinesDisplayPrefs:
    # 去重并保持顺序稳定
    hidden = list(dict.fromkeys(body.hidden_agent_ids))
    prefs = await session.get(UserMachinesDisplayPrefs, user)
    if prefs is None:
        prefs = UserMachinesDisplayPrefs(
            user_id=user,
            show_stat_cards=body.show_stat_cards,
            show_machine_cards=body.show_machine_cards,
            hidden_agent_ids=hidden,
        )
        session.add(prefs)
    else:
        prefs.show_stat_cards = body.show_stat_cards
        prefs.show_machine_cards = body.show_machine_cards
        prefs.hidden_agent_ids = hidden
    await session.commit()
    await session.refresh(prefs)
    return MachinesDisplayPrefs.model_validate(prefs)
