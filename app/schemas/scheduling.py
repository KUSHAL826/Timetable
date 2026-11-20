from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class ValidationItem(BaseModel):
    module: str
    status: str = Field(..., pattern="^(complete|warning|error)$")
    title: str
    message: str
    count: int = 0
    link: str
    is_blocking: bool = False
    details: List[str] = []

class ValidationDashboardResponse(BaseModel):
    is_valid: bool
    blocking_error_count: int
    warning_count: int
    complete_count: int
    modules: List[ValidationItem]

class TimetableGenerationRequest(BaseModel):
    cluster_id: str
    semester_id: str
    solver_timeout_seconds: int = 60
    allow_soft_relaxations: bool = False

class TimetableEntryResponse(BaseModel):
    id: str
    generation_id: str
    section_id: str
    section_name: str
    subject_id: str
    subject_code: str
    subject_name: str
    faculty_id: Optional[str] = None
    faculty_name: Optional[str] = None
    co_faculty_names: List[str] = []
    classroom_id: Optional[str] = None
    room_code: Optional[str] = None
    laboratory_id: Optional[str] = None
    lab_name: Optional[str] = None
    lab_batch_id: Optional[str] = None
    batch_name: Optional[str] = None
    time_slot_id: str
    day_of_week: int
    period_number: int
    start_time: str
    end_time: str
    entry_type: str = "regular"

class ConflictItem(BaseModel):
    id: Optional[str] = None
    severity: str = Field("error", pattern="^(error|warning|info)$")
    conflict_type: str
    description: str
    related_entity_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

class TimetableGenerationResponse(BaseModel):
    generation_id: str
    status: str
    solver_status: str
    solve_time_seconds: float
    entries_count: int
    conflicts: List[ConflictItem] = []
    warnings: List[str] = []

class TimetableManualEditRequest(BaseModel):
    entry_id: str
    new_time_slot_id: Optional[str] = None
    new_faculty_id: Optional[str] = None
    new_classroom_id: Optional[str] = None
    new_laboratory_id: Optional[str] = None
    new_lab_batch_id: Optional[str] = None

class TimetableApprovalRequest(BaseModel):
    generation_id: str
    action: str = Field(..., pattern="^(submit|approve|reject|publish|archive)$")
    comments: Optional[str] = None
