"""用户权限管理API路由"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..dependencies import get_app_state
from ...services.user_permission_service import UserPermissionService
from .config import verify_api_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/users", tags=["users"])


def _get_service(request: Request) -> UserPermissionService:
    state = get_app_state()
    if not hasattr(state, "user_permission_service") or state.user_permission_service is None:
        logger.error("User permission service not initialized")
        raise HTTPException(status_code=500, detail="用户权限服务未初始化")
    return state.user_permission_service


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    success: bool
    message: str
    user: Optional[Dict[str, Any]] = None


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=32)
    password: str = Field(..., min_length=4, max_length=64)
    role_name: str
    display_name: Optional[str] = None
    email: Optional[str] = None


class UserUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    email: Optional[str] = None
    role_name: Optional[str] = None
    status: Optional[str] = None


class PasswordChangeRequest(BaseModel):
    new_password: str = Field(..., min_length=4, max_length=64)


class RoleCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=32)
    display_name: str
    description: Optional[str] = None
    permissions: Optional[Dict[str, Dict[str, bool]]] = None


class RoleUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    permissions: Optional[Dict[str, Dict[str, bool]]] = None


class PermissionMatrixUpdateRequest(BaseModel):
    role_name: str
    permissions: Dict[str, Dict[str, bool]]


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, request: Request):
    svc = _get_service(request)
    user = await svc.authenticate(req.username, req.password)
    if user is None:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return LoginResponse(success=True, message="登录成功", user=user)


@router.get("/list")
async def list_users(request: Request, _token: str = Depends(verify_api_token)):
    svc = _get_service(request)
    users = await svc.list_users()
    return {"count": len(users), "users": users}


@router.get("/{user_id}")
async def get_user(user_id: int, request: Request, _token: str = Depends(verify_api_token)):
    svc = _get_service(request)
    user = await svc.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


@router.post("/create")
async def create_user(req: UserCreateRequest, request: Request, _token: str = Depends(verify_api_token)):
    svc = _get_service(request)
    try:
        user = await svc.create_user(
            username=req.username,
            password=req.password,
            role_name=req.role_name,
            display_name=req.display_name,
            email=req.email,
        )
        return {"success": True, "message": "用户创建成功", "user": user}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{user_id}")
async def update_user(user_id: int, req: UserUpdateRequest, request: Request, _token: str = Depends(verify_api_token)):
    svc = _get_service(request)
    try:
        user = await svc.update_user(
            user_id=user_id,
            display_name=req.display_name,
            email=req.email,
            role_name=req.role_name,
            status=req.status,
        )
        if user is None:
            raise HTTPException(status_code=404, detail="用户不存在")
        return {"success": True, "message": "用户更新成功", "user": user}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{user_id}")
async def delete_user(user_id: int, request: Request, _token: str = Depends(verify_api_token)):
    svc = _get_service(request)
    try:
        deleted = await svc.delete_user(user_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="用户不存在")
        return {"success": True, "message": "用户删除成功"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{user_id}/password")
async def change_password(user_id: int, req: PasswordChangeRequest, request: Request, _token: str = Depends(verify_api_token)):
    svc = _get_service(request)
    user = await svc.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    await svc.change_password(user_id, req.new_password)
    return {"success": True, "message": "密码修改成功"}


@router.get("/roles/list")
async def list_roles(request: Request, _token: str = Depends(verify_api_token)):
    svc = _get_service(request)
    roles = await svc.list_roles()
    return {"count": len(roles), "roles": roles}


@router.get("/roles/{role_name}")
async def get_role(role_name: str, request: Request, _token: str = Depends(verify_api_token)):
    svc = _get_service(request)
    role = await svc.get_role(role_name)
    if role is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    return role


@router.post("/roles/create")
async def create_role(req: RoleCreateRequest, request: Request, _token: str = Depends(verify_api_token)):
    svc = _get_service(request)
    try:
        role = await svc.create_role(
            name=req.name,
            display_name=req.display_name,
            description=req.description,
            permissions=req.permissions,
        )
        return {"success": True, "message": "角色创建成功", "role": role}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/roles/{role_name}")
async def update_role(role_name: str, req: RoleUpdateRequest, request: Request, _token: str = Depends(verify_api_token)):
    svc = _get_service(request)
    try:
        role = await svc.update_role(
            role_name=role_name,
            display_name=req.display_name,
            description=req.description,
            permissions=req.permissions,
        )
        if role is None:
            raise HTTPException(status_code=404, detail="角色不存在")
        return {"success": True, "message": "角色更新成功", "role": role}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/roles/{role_name}")
async def delete_role(role_name: str, request: Request, _token: str = Depends(verify_api_token)):
    svc = _get_service(request)
    try:
        deleted = await svc.delete_role(role_name)
        if not deleted:
            raise HTTPException(status_code=404, detail="角色不存在")
        return {"success": True, "message": "角色删除成功"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/permissions/matrix")
async def get_permission_matrix(request: Request, _token: str = Depends(verify_api_token)):
    svc = _get_service(request)
    return await svc.get_permission_matrix()


@router.put("/permissions/matrix")
async def update_permission_matrix(req: PermissionMatrixUpdateRequest, request: Request, _token: str = Depends(verify_api_token)):
    svc = _get_service(request)
    try:
        role = await svc.update_permission_matrix(req.role_name, req.permissions)
        if role is None:
            raise HTTPException(status_code=404, detail="角色不存在")
        return {"success": True, "message": "权限矩阵更新成功", "role": role}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/permissions/check")
async def check_permission(username: str, resource: str, action: str, request: Request, _token: str = Depends(verify_api_token)):
    svc = _get_service(request)
    allowed = await svc.check_permission(username, resource, action)
    return {"username": username, "resource": resource, "action": action, "allowed": allowed}


@router.get("/{username}/permissions")
async def get_user_permissions(username: str, request: Request, _token: str = Depends(verify_api_token)):
    svc = _get_service(request)
    permissions = await svc.get_user_permissions(username)
    return {"username": username, "permissions": permissions}
