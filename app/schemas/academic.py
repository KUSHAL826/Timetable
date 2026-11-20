from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from uuid import UUID

class DepartmentSchema(BaseModel):
    id: Optional[Union[int, str]] = None
    name: str
    code: Optional[str] = None

class AcademicYearSchema(BaseModel):
    id: Optional[str] = None
    name: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_active: bool = False

class SemesterSchema(BaseModel):
    id: Optional[str] = None
    semester_number: int
    academic_year_id: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class ClusterSchema(BaseModel):
    id: Optional[str] = None
    name: str
    department_id: Optional[str] = None
    semester_id: str
    description: Optional[str] = None
    is_active: bool = True
    section_ids: List[str] = []

class SectionSchema(BaseModel):
    id: Optional[str] = None
    name: str
    department_id: Optional[str] = None
    semester_id: str
    student_strength: int = Field(..., gt=0)
    cluster_id: Optional[str] = None

class FacultyCreateSchema(BaseModel):
    employee_id: str
    full_name: str
    department_id: Optional[str] = None
    phone_number: str
    email: Optional[str] = None
    max_weekly_hours: int = 20
    qualified_subject_ids: List[str] = []

class FacultyResponseSchema(BaseModel):
    id: str
    employee_id: str
    full_name: str
    department_id: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    max_weekly_hours: int = 20
    is_active: bool = True
    qualified_subjects: List[str] = []

class SubjectSchema(BaseModel):
    id: Optional[str] = None
    subject_code: str
    subject_name: str
    subject_type: str = Field(..., pattern="^(theory|practical|elective)$")
    weekly_hours: int = Field(..., ge=0)
    consecutive_periods: int = Field(1, ge=1)
    department_id: Optional[str] = None
    credits: int = 3
    semester_id: Optional[str] = None
    is_active: bool = True

class ClassroomSchema(BaseModel):
    id: Optional[str] = None
    room_code: str
    room_name: Optional[str] = None
    capacity: int = Field(..., gt=0)
    room_type: str = "classroom"
    is_active: bool = True

class LaboratorySchema(BaseModel):
    id: Optional[str] = None
    lab_code: str
    lab_name: str
    lab_type: Optional[str] = None
    student_capacity: int = Field(..., gt=0)
    workstation_capacity: Optional[int] = None
    equipment_details: Optional[str] = None
    supported_subject_ids: List[str] = []
    is_active: bool = True

class LabStaffingSchema(BaseModel):
    id: Optional[str] = None
    section_id: str
    subject_id: str
    lab_id: str
    primary_faculty_id: str
    required_co_teacher_count: int = Field(0, ge=0)
    co_teacher_ids: List[str] = []
    weekly_hours: int = Field(..., gt=0)
    consecutive_periods: int = Field(2, ge=1)
    students_per_batch: Optional[int] = None

class LabBatchSchema(BaseModel):
    id: Optional[str] = None
    section_id: str
    batch_name: str
    student_count: int = Field(..., gt=0)

class ElectiveGroupSchema(BaseModel):
    id: Optional[str] = None
    semester_id: str
    group_name: str
    is_active: bool = True
    options: List[Dict[str, Any]] = []

class TimeSlotSchema(BaseModel):
    id: Optional[str] = None
    day_of_week: int = Field(..., ge=1, le=7)
    period_number: int = Field(..., ge=1)
    start_time: str
    end_time: str
    slot_type: str = "class"
    is_schedulable: bool = True
