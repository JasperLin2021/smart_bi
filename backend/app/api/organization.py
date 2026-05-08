from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.auth import get_current_user
from app.core.audit import try_record_audit_log
from app.core.permissions import require_super_admin
from app.core.safe_delete import assert_organization_can_delete
from app.db.session import get_db
from app.models.organization import Organization
from app.models.user import User
from app.schemas.organization import OrganizationCreate, OrganizationUpdate, OrganizationOut

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get("", response_model=list[OrganizationOut])
def list_organizations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_super_admin(current_user)
    return db.query(Organization).all()


@router.post("", response_model=OrganizationOut, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: OrganizationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_super_admin(current_user)
    if db.query(Organization).filter(Organization.slug == payload.slug).first():
        raise HTTPException(status_code=400, detail="Slug已存在")
    org = Organization(name=payload.name, slug=payload.slug)
    db.add(org)
    db.commit()
    db.refresh(org)
    try_record_audit_log(
        db,
        actor=current_user,
        action="organization.create",
        resource_type="organization",
        resource_id=org.id,
        resource_name=org.name,
        org_id=org.id,
        message="企业已创建",
        detail={"slug": org.slug},
    )
    return org


@router.get("/{org_id}", response_model=OrganizationOut)
def get_organization(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_super_admin(current_user)
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="企业不存在")
    return org


@router.put("/{org_id}", response_model=OrganizationOut)
def update_organization(
    org_id: int,
    payload: OrganizationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_super_admin(current_user)
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="企业不存在")
    if payload.name is not None:
        org.name = payload.name
    if payload.slug is not None:
        if db.query(Organization).filter(Organization.slug == payload.slug, Organization.id != org_id).first():
            raise HTTPException(status_code=400, detail="Slug已存在")
        org.slug = payload.slug
    db.commit()
    db.refresh(org)
    try_record_audit_log(
        db,
        actor=current_user,
        action="organization.update",
        resource_type="organization",
        resource_id=org.id,
        resource_name=org.name,
        org_id=org.id,
        message="企业已更新",
        detail={"fields": list(payload.model_dump(exclude_unset=True).keys())},
    )
    return org


@router.delete("/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_organization(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_super_admin(current_user)
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="企业不存在")
    assert_organization_can_delete(db, org)
    org_name = org.name
    org_slug = org.slug
    db.delete(org)
    db.commit()
    try_record_audit_log(
        db,
        actor=current_user,
        action="organization.delete",
        resource_type="organization",
        resource_id=org_id,
        resource_name=org_name,
        org_id=org_id,
        message="企业已删除",
        detail={"slug": org_slug},
    )
