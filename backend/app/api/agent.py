import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.agent_planner import build_agent_context, plan_agent_actions
from app.core.agent_skills import install_skill_from_github, list_agent_skills
from app.db.session import get_db
from app.models.agent_run import AgentRun
from app.models.datasource import DataSource
from app.models.llm_setting import LlmSetting
from app.models.user import User
from app.schemas.agent import AgentPlanRequest, AgentPlanResponse, AgentRunCompleteRequest
from app.schemas.agent_skill import AgentSkillInstallRequest, AgentSkillOut

router = APIRouter(prefix="/agent", tags=["agent"])


@router.get("/skills", response_model=list[AgentSkillOut])
def list_skills(
    current_user: User = Depends(get_current_user),
):
    return list_agent_skills()


@router.post("/skills/install", response_model=AgentSkillOut)
async def install_skill(
    payload: AgentSkillInstallRequest,
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "super_admin":
        raise HTTPException(status_code=403, detail="只有超级管理员可以安装 skills")
    try:
        return await install_skill_from_github(payload.source)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/plan", response_model=AgentPlanResponse)
async def plan_actions(
    payload: AgentPlanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    datasource_names = [item.name for item in db.query(DataSource).filter(DataSource.is_active == 1).all()]
    llm_setting = db.query(LlmSetting).first()
    context = build_agent_context(
        role=current_user.role,
        route=payload.route,
        datasource_id=payload.datasource_id,
        datasource_name=payload.datasource_name,
        datasource_names=datasource_names,
        agent_planner_mode=(llm_setting.agent_planner_mode if llm_setting else "llm_only"),
    )
    plan = await plan_agent_actions(payload.message, context)

    run = AgentRun(
        user_id=current_user.id,
        route=payload.route,
        prompt=payload.message,
        plan_json=json.dumps(plan, ensure_ascii=False),
        status="planned",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    return {"run_id": run.id, **plan}


@router.post("/runs/{run_id}/complete")
def complete_run(
    run_id: int,
    payload: AgentRunCompleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    run = (
        db.query(AgentRun)
        .filter(AgentRun.id == run_id, AgentRun.user_id == current_user.id)
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail="Agent 运行记录不存在")

    run.status = payload.status
    run.execution_json = json.dumps(payload.execution, ensure_ascii=False)
    db.commit()
    return {"status": "ok"}
