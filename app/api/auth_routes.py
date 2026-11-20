import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, status
from app.schemas.auth import LoginRequest, PasswordChangeRequest, TokenResponse, UserProfileResponse
from app.auth.security import verify_password, get_password_hash, create_access_token
from app.auth.dependencies import get_current_user
from app.services.data_store import store
from app.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    """
    Authenticates Timetable Officer or Teacher using Employee/Teacher ID.
    Enforces initial temporary password for officer (8296060284) and registered phone for teacher.
    """
    employee_id = req.employee_id.strip()
    profile = store.profiles.get(employee_id)

    if not profile or not profile.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Employee ID or account is inactive."
        )

    # Verify password against hash
    if not verify_password(req.password, profile["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials provided."
        )

    # Issue JWT token with role claims
    token_payload = {
        "sub": profile["id"],
        "employee_id": profile["employee_id"],
        "role": profile["role"],
        "full_name": profile["full_name"],
        "must_change_password": profile["must_change_password"]
    }
    access_token = create_access_token(token_payload)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        role=profile["role"],
        employee_id=profile["employee_id"],
        full_name=profile["full_name"],
        must_change_password=profile["must_change_password"],
        user_id=profile["id"]
    )

@router.post("/change-password")
async def change_password(
    req: PasswordChangeRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Enforces mandatory password rotation on first login and on-demand for both roles.
    """
    employee_id = current_user.get("employee_id")
    profile = store.profiles.get(employee_id)
    if not profile:
        raise HTTPException(status_code=404, detail="User profile not found")

    if not verify_password(req.old_password, profile["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    if req.old_password == req.new_password:
        raise HTTPException(status_code=400, detail="New password cannot be identical to the old password")

    # Update credentials
    profile["password_hash"] = get_password_hash(req.new_password)
    profile["must_change_password"] = False
    profile["updated_at"] = datetime.utcnow().isoformat()

    # Log action
    store.audit_logs.append({
        "id": str(uuid.uuid4()),
        "actor_id": profile["id"],
        "action": "PASSWORD_CHANGED",
        "entity_type": "profile",
        "entity_id": profile["id"],
        "details": {"employee_id": employee_id},
        "created_at": datetime.utcnow().isoformat()
    })

    return {"status": "success", "message": "Password updated successfully. You now have full access."}

@router.get("/me", response_model=UserProfileResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Returns profile for the currently authenticated user."""
    employee_id = current_user.get("employee_id")
    profile = store.profiles.get(employee_id)
    if not profile:
        raise HTTPException(status_code=404, detail="User profile not found")

    return UserProfileResponse(
        id=profile["id"],
        employee_id=profile["employee_id"],
        full_name=profile["full_name"],
        role=profile["role"],
        phone_number=profile.get("phone_number"),
        must_change_password=profile.get("must_change_password", False),
        is_active=profile.get("is_active", True)
    )
