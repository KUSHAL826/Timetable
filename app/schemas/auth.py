from pydantic import BaseModel, Field
from typing import Optional

class LoginRequest(BaseModel):
    employee_id: str = Field(..., description="Teacher ID or Officer ID")
    password: str = Field(..., description="User password (phone number for initial teacher login)")

class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8, description="Minimum 8 characters with letters, numbers, and symbols")

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    employee_id: str
    full_name: str
    must_change_password: bool
    user_id: str

class UserProfileResponse(BaseModel):
    id: str
    employee_id: str
    full_name: str
    role: str
    phone_number: Optional[str] = None
    must_change_password: bool
    is_active: bool
