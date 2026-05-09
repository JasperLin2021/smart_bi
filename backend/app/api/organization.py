from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.api.auth import get_current_user
from app.core.audit import try_record_audit_log
from app.core.permissions import require_org_admin_or_above, require_super_admin
from app.core.safe_delete import assert_organization_can_delete
from app.db.session import get_db
from app.models.organization import Department, Organization
from app.models.user import User
from app.schemas.organization import (
    DepartmentCreate,
    DepartmentOut,
    DepartmentUpdate,
    OrganizationCreate,
    OrganizationOut,
    OrganizationUpdate,
)

router = APIRouter(prefix="/organizations", tags=["organizations"])


def _load_org_for_department_management(db: Session, org_id: int, current_user: User) -> Organization:
    require_org_admin_or_above(current_user)
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="企业不存在")
    if current_user.role != "super_admin" and current_user.org_id != org_id:
        raise HTTPException(status_code=403, detail="只能管理本企业组织架构")
    return org


def _load_department(db: Session, org_id: int, department_id: int) -> Department:
    department = (
        db.query(Department)
        .filter(Department.id == department_id, Department.org_id == org_id)
        .first()
    )
    if not department:
        raise HTTPException(status_code=404, detail="部门不存在")
    return department


def _sibling_name_exists(
    db: Session,
    *,
    org_id: int,
    name: str,
    parent_id: int | None,
    exclude_id: int | None = None,
) -> bool:
    query = db.query(Department).filter(
        Department.org_id == org_id,
        Department.name == name,
    )
    if parent_id is None:
        query = query.filter(Department.parent_id.is_(None))
    else:
        query = query.filter(Department.parent_id == parent_id)
    if exclude_id is not None:
        query = query.filter(Department.id != exclude_id)
    return query.first() is not None


def _next_sort_order(db: Session, org_id: int, parent_id: int | None) -> int:
    query = db.query(func.max(Department.sort_order)).filter(Department.org_id == org_id)
    if parent_id is None:
        query = query.filter(Department.parent_id.is_(None))
    else:
        query = query.filter(Department.parent_id == parent_id)
    current = query.scalar()
    return int(current or 0) + 1


def _department_descendant_ids(db: Session, org_id: int, department_id: int) -> set[int]:
    descendants: set[int] = set()
    frontier = [department_id]
    while frontier:
        children = (
            db.query(Department.id)
            .filter(Department.org_id == org_id, Department.parent_id.in_(frontier))
            .all()
        )
        frontier = [item[0] for item in children if item[0] not in descendants]
        descendants.update(frontier)
    return descendants


def _build_department_nodes(departments: list[Department], user_counts: dict[int, int]) -> list[dict]:
    by_parent: dict[int | None, list[Department]] = {}
    by_id = {department.id: department for department in departments}
    for department in departments:
        parent_id = department.parent_id if department.parent_id in by_id else None
        by_parent.setdefault(parent_id, []).append(department)

    for siblings in by_parent.values():
        siblings.sort(key=lambda item: (item.sort_order or 0, item.id))

    def build(department: Department) -> dict:
        children = [build(child) for child in by_parent.get(department.id, [])]
        return {
            "id": department.id,
            "node_key": f"dept-{department.id}",
            "type": "department",
            "name": department.name,
            "label": department.name,
            "org_id": department.org_id,
            "parent_id": department.parent_id,
            "sort_order": department.sort_order or 0,
            "user_count": user_counts.get(department.id, 0),
            "department_count": len(children),
            "children": children,
        }

    return [build(department) for department in by_parent.get(None, [])]


def _organization_tree_payload(db: Session, organizations: list[Organization]) -> list[dict]:
    if not organizations:
        return []
    org_ids = [org.id for org in organizations]
    departments = (
        db.query(Department)
        .filter(Department.org_id.in_(org_ids))
        .order_by(Department.org_id.asc(), Department.sort_order.asc(), Department.id.asc())
        .all()
    )
    departments_by_org: dict[int, list[Department]] = {}
    for department in departments:
        departments_by_org.setdefault(department.org_id, []).append(department)

    org_user_counts = {
        org_id: count
        for org_id, count in (
            db.query(User.org_id, func.count(User.id))
            .filter(User.org_id.in_(org_ids))
            .group_by(User.org_id)
            .all()
        )
    }
    department_user_counts = {
        department_id: count
        for department_id, count in (
            db.query(User.department_id, func.count(User.id))
            .filter(User.department_id.isnot(None))
            .group_by(User.department_id)
            .all()
        )
    }

    payload: list[dict] = []
    for org in sorted(organizations, key=lambda item: item.id):
        org_departments = departments_by_org.get(org.id, [])
        payload.append({
            "id": org.id,
            "node_key": f"org-{org.id}",
            "type": "organization",
            "name": org.name,
            "label": org.name,
            "slug": org.slug,
            "org_id": org.id,
            "parent_id": None,
            "sort_order": 0,
            "user_count": org_user_counts.get(org.id, 0),
            "department_count": len(org_departments),
            "children": _build_department_nodes(org_departments, department_user_counts),
        })
    return payload


@router.get("", response_model=list[OrganizationOut])
def list_organizations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_super_admin(current_user)
    return db.query(Organization).all()


@router.get("/tree", response_model=list[dict])
def get_organization_tree(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_org_admin_or_above(current_user)
    if current_user.role == "super_admin":
        organizations = db.query(Organization).order_by(Organization.id.asc()).all()
    else:
        if current_user.org_id is None:
            raise HTTPException(status_code=403, detail="当前用户未绑定企业")
        organizations = (
            db.query(Organization)
            .filter(Organization.id == current_user.org_id)
            .order_by(Organization.id.asc())
            .all()
        )
    return _organization_tree_payload(db, organizations)


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


@router.get("/{org_id}/departments", response_model=list[DepartmentOut])
def list_departments(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _load_org_for_department_management(db, org_id, current_user)
    return (
        db.query(Department)
        .filter(Department.org_id == org_id)
        .order_by(Department.parent_id.asc(), Department.sort_order.asc(), Department.id.asc())
        .all()
    )


@router.post("/{org_id}/departments", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
def create_department(
    org_id: int,
    payload: DepartmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org = _load_org_for_department_management(db, org_id, current_user)
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="部门名称不能为空")
    if payload.parent_id is not None:
        _load_department(db, org_id, payload.parent_id)
    if _sibling_name_exists(db, org_id=org_id, name=name, parent_id=payload.parent_id):
        raise HTTPException(status_code=400, detail="同级部门名称已存在")

    department = Department(
        name=name,
        org_id=org_id,
        parent_id=payload.parent_id,
        sort_order=payload.sort_order if payload.sort_order is not None else _next_sort_order(db, org_id, payload.parent_id),
    )
    db.add(department)
    db.commit()
    db.refresh(department)
    try_record_audit_log(
        db,
        actor=current_user,
        action="department.create",
        resource_type="department",
        resource_id=department.id,
        resource_name=department.name,
        org_id=org.id,
        message="部门已创建",
        detail={"parent_id": department.parent_id},
    )
    return department


@router.put("/{org_id}/departments/{department_id}", response_model=DepartmentOut)
def update_department(
    org_id: int,
    department_id: int,
    payload: DepartmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _load_org_for_department_management(db, org_id, current_user)
    department = _load_department(db, org_id, department_id)

    next_name = payload.name.strip() if payload.name is not None else department.name
    if not next_name:
        raise HTTPException(status_code=400, detail="部门名称不能为空")

    next_parent_id = department.parent_id
    if "parent_id" in payload.model_fields_set:
        next_parent_id = payload.parent_id
        if next_parent_id == department.id:
            raise HTTPException(status_code=400, detail="上级部门不能是自己")
        if next_parent_id is not None:
            _load_department(db, org_id, next_parent_id)
            if next_parent_id in _department_descendant_ids(db, org_id, department.id):
                raise HTTPException(status_code=400, detail="上级部门不能选择当前部门的下级部门")

    if _sibling_name_exists(db, org_id=org_id, name=next_name, parent_id=next_parent_id, exclude_id=department.id):
        raise HTTPException(status_code=400, detail="同级部门名称已存在")

    department.name = next_name
    department.parent_id = next_parent_id
    if payload.sort_order is not None:
        department.sort_order = payload.sort_order
    db.query(User).filter(User.department_id == department.id).update(
        {"department": department.name},
        synchronize_session=False,
    )
    db.commit()
    db.refresh(department)
    try_record_audit_log(
        db,
        actor=current_user,
        action="department.update",
        resource_type="department",
        resource_id=department.id,
        resource_name=department.name,
        org_id=department.org_id,
        message="部门已更新",
        detail={"fields": list(payload.model_dump(exclude_unset=True).keys())},
    )
    return department


@router.delete("/{org_id}/departments/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(
    org_id: int,
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _load_org_for_department_management(db, org_id, current_user)
    department = _load_department(db, org_id, department_id)
    child_count = db.query(Department).filter(Department.parent_id == department.id).count()
    user_count = db.query(User).filter(User.department_id == department.id).count()
    blockers: list[str] = []
    if child_count:
        blockers.append(f"{child_count} 个下级部门")
    if user_count:
        blockers.append(f"{user_count} 个用户")
    if blockers:
        raise HTTPException(
            status_code=409,
            detail=f"无法删除部门「{department.name}」，仍被{'; '.join(blockers)}引用。请先迁移或删除这些引用。",
        )

    department_name = department.name
    db.delete(department)
    db.commit()
    try_record_audit_log(
        db,
        actor=current_user,
        action="department.delete",
        resource_type="department",
        resource_id=department_id,
        resource_name=department_name,
        org_id=org_id,
        message="部门已删除",
    )


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
