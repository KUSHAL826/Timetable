import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from app.auth.dependencies import require_officer, get_current_user
from app.auth.security import get_password_hash
from app.services.data_store import store
from app.schemas.academic import (
    DepartmentSchema, AcademicYearSchema, SemesterSchema, ClusterSchema,
    SectionSchema, FacultyCreateSchema, FacultyResponseSchema, SubjectSchema,
    ClassroomSchema, LaboratorySchema, LabStaffingSchema, LabBatchSchema,
    ElectiveGroupSchema, TimeSlotSchema
)

router = APIRouter(prefix="/academic", tags=["Academic Setup & Master Data"])

# 1. DEPARTMENTS
@router.get("/departments", response_model=List[DepartmentSchema])
async def list_departments():
    return list(store.departments.values())

@router.post("/departments", response_model=DepartmentSchema)
async def create_department(dept: DepartmentSchema, user: dict = Depends(require_officer)):
    dept_id = str(dept.id) if dept.id else str(store.get_next_dept_id())
    store.departments[dept_id] = {
        "id": int(dept_id) if dept_id.isdigit() else dept_id,
        "name": dept.name,
        "code": dept.code,
        "created_at": datetime.utcnow().isoformat()
    }
    return store.departments[dept_id]

# 2. ACADEMIC YEARS & SEMESTERS
@router.get("/academic-years", response_model=List[AcademicYearSchema])
async def list_academic_years():
    return list(store.academic_years.values())

@router.post("/academic-years", response_model=AcademicYearSchema)
async def create_academic_year(ay: AcademicYearSchema, user: dict = Depends(require_officer)):
    ay_id = ay.id or str(uuid.uuid4())
    store.academic_years[ay_id] = {
        "id": ay_id,
        "name": ay.name,
        "start_date": ay.start_date,
        "end_date": ay.end_date,
        "is_active": ay.is_active
    }
    return store.academic_years[ay_id]

@router.get("/semesters", response_model=List[SemesterSchema])
async def list_semesters():
    return list(store.semesters.values())

@router.post("/semesters", response_model=SemesterSchema)
async def create_semester(sem: SemesterSchema, user: dict = Depends(require_officer)):
    sem_id = sem.id or str(uuid.uuid4())
    store.semesters[sem_id] = {
        "id": sem_id,
        "semester_number": sem.semester_number,
        "academic_year_id": sem.academic_year_id,
        "start_date": sem.start_date,
        "end_date": sem.end_date
    }
    return store.semesters[sem_id]

# 3. CLUSTERS
@router.get("/clusters", response_model=List[ClusterSchema])
async def list_clusters():
    res = []
    for c in store.clusters.values():
        c_copy = c.copy()
        c_copy["section_ids"] = [
            cs["section_id"] for cs in store.cluster_sections if cs["cluster_id"] == c["id"]
        ]
        res.append(c_copy)
    return res

@router.post("/clusters", response_model=ClusterSchema)
async def create_cluster(cluster: ClusterSchema, user: dict = Depends(require_officer)):
    c_id = cluster.id or str(uuid.uuid4())
    store.clusters[c_id] = {
        "id": c_id,
        "name": cluster.name,
        "department_id": cluster.department_id,
        "semester_id": cluster.semester_id,
        "description": cluster.description,
        "is_active": cluster.is_active,
        "created_at": datetime.utcnow().isoformat()
    }
    # map sections
    store.cluster_sections = [cs for cs in store.cluster_sections if cs["cluster_id"] != c_id]
    for sec_id in cluster.section_ids:
        store.cluster_sections.append({"cluster_id": c_id, "section_id": sec_id})
        if sec_id in store.sections:
            store.sections[sec_id]["cluster_id"] = c_id

    result = store.clusters[c_id].copy()
    result["section_ids"] = cluster.section_ids
    return result

# 4. SECTIONS
@router.get("/sections", response_model=List[SectionSchema])
async def list_sections():
    return list(store.sections.values())

@router.post("/sections", response_model=SectionSchema)
async def create_section(sec: SectionSchema, user: dict = Depends(require_officer)):
    sec_id = sec.id or str(uuid.uuid4())
    store.sections[sec_id] = {
        "id": sec_id,
        "name": sec.name,
        "department_id": sec.department_id,
        "semester_id": sec.semester_id,
        "student_strength": sec.student_strength,
        "cluster_id": sec.cluster_id
    }
    if sec.cluster_id:
        store.cluster_sections.append({"cluster_id": sec.cluster_id, "section_id": sec_id})
    return store.sections[sec_id]

# 5. FACULTY MANAGEMENT (With Transactional Auth Account Creation)
@router.get("/faculty", response_model=List[FacultyResponseSchema])
async def list_faculty():
    res = []
    for f in store.faculty.values():
        qual_subs = [
            fs["subject_id"] for fs in store.faculty_subjects.values()
            if fs["faculty_id"] == f["id"] and fs.get("is_qualified", True)
        ]
        res.append(FacultyResponseSchema(
            id=f["id"],
            employee_id=f["employee_id"],
            full_name=f["full_name"],
            department_id=f.get("department_id"),
            phone_number=f.get("phone_number"),
            email=f.get("email"),
            max_weekly_hours=f.get("max_weekly_hours", 20),
            is_active=f.get("is_active", True),
            qualified_subjects=qual_subs
        ))
    return res

@router.post("/faculty", response_model=FacultyResponseSchema)
async def create_faculty(fac: FacultyCreateSchema, user: dict = Depends(require_officer)):
    emp_id = fac.employee_id.strip()
    if emp_id in store.profiles:
        raise HTTPException(status_code=400, detail=f"Employee ID {emp_id} is already registered.")

    fac_id = str(uuid.uuid4())
    # Save faculty record
    store.faculty[fac_id] = {
        "id": fac_id,
        "employee_id": emp_id,
        "full_name": fac.full_name,
        "department_id": fac.department_id,
        "phone_number": fac.phone_number,
        "email": fac.email or f"{emp_id.lower()}@college.edu",
        "max_weekly_hours": fac.max_weekly_hours,
        "preferred_periods": [1, 2, 3],
        "unavailable_periods": [],
        "is_active": True,
        "created_at": datetime.utcnow().isoformat()
    }

    # Transactionally create corresponding Teacher Profile with Phone Number as initial password
    store.profiles[emp_id] = {
        "id": fac_id,
        "employee_id": emp_id,
        "full_name": fac.full_name,
        "role": "teacher",
        "phone_number": fac.phone_number,
        "password_hash": get_password_hash(fac.phone_number),
        "must_change_password": True,
        "is_active": True,
        "created_at": datetime.utcnow().isoformat()
    }

    # Save qualifications
    for sub_id in fac.qualified_subject_ids:
        store.faculty_subjects[f"{fac_id}_{sub_id}"] = {
            "faculty_id": fac_id,
            "subject_id": sub_id,
            "is_qualified": True
        }

    return FacultyResponseSchema(
        id=fac_id,
        employee_id=emp_id,
        full_name=fac.full_name,
        department_id=fac.department_id,
        phone_number=fac.phone_number,
        email=fac.email,
        max_weekly_hours=fac.max_weekly_hours,
        is_active=True,
        qualified_subjects=fac.qualified_subject_ids
    )

# 6. SUBJECTS
@router.get("/subjects", response_model=List[SubjectSchema])
async def list_subjects():
    return list(store.subjects.values())

@router.post("/subjects", response_model=SubjectSchema)
async def create_subject(sub: SubjectSchema, user: dict = Depends(require_officer)):
    sub_id = sub.id or str(uuid.uuid4())
    store.subjects[sub_id] = {
        "id": sub_id,
        "subject_code": sub.subject_code,
        "subject_name": sub.subject_name,
        "subject_type": sub.subject_type,
        "weekly_hours": sub.weekly_hours,
        "consecutive_periods": sub.consecutive_periods,
        "department_id": sub.department_id,
        "credits": sub.credits,
        "semester_id": sub.semester_id,
        "is_active": sub.is_active
    }
    return store.subjects[sub_id]

# 7. CLASSROOMS & LABORATORIES
@router.get("/classrooms", response_model=List[ClassroomSchema])
async def list_classrooms():
    return list(store.classrooms.values())

@router.post("/classrooms", response_model=ClassroomSchema)
async def create_classroom(cr: ClassroomSchema, user: dict = Depends(require_officer)):
    r_id = cr.id or str(uuid.uuid4())
    store.classrooms[r_id] = {
        "id": r_id,
        "room_code": cr.room_code,
        "room_name": cr.room_name,
        "capacity": cr.capacity,
        "room_type": cr.room_type,
        "is_active": cr.is_active
    }
    return store.classrooms[r_id]

@router.get("/laboratories", response_model=List[LaboratorySchema])
async def list_laboratories():
    return list(store.laboratories.values())

@router.post("/laboratories", response_model=LaboratorySchema)
async def create_laboratory(lab: LaboratorySchema, user: dict = Depends(require_officer)):
    l_id = lab.id or str(uuid.uuid4())
    store.laboratories[l_id] = {
        "id": l_id,
        "lab_code": lab.lab_code,
        "lab_name": lab.lab_name,
        "lab_type": lab.lab_type,
        "student_capacity": lab.student_capacity,
        "workstation_capacity": lab.workstation_capacity or lab.student_capacity,
        "equipment_details": lab.equipment_details,
        "is_active": lab.is_active
    }
    return store.laboratories[l_id]

# 8. LAB STAFFING & BATCHES
@router.get("/lab-staffing", response_model=List[LabStaffingSchema])
async def list_lab_staffing():
    return list(store.lab_staffing_requirements.values())

@router.post("/lab-staffing", response_model=LabStaffingSchema)
async def configure_lab_staffing(staff: LabStaffingSchema, user: dict = Depends(require_officer)):
    req_id = staff.id or str(uuid.uuid4())
    # Validate assigned co-teachers match required count
    if len(staff.co_teacher_ids) != staff.required_co_teacher_count:
        raise HTTPException(
            status_code=400,
            detail=f"Configured required co-teachers count ({staff.required_co_teacher_count}) must match assigned co-teachers list ({len(staff.co_teacher_ids)} assigned)."
        )

    store.lab_staffing_requirements[req_id] = {
        "id": req_id,
        "section_id": staff.section_id,
        "subject_id": staff.subject_id,
        "lab_id": staff.lab_id,
        "primary_faculty_id": staff.primary_faculty_id,
        "required_co_teacher_count": staff.required_co_teacher_count,
        "co_teacher_ids": staff.co_teacher_ids,
        "weekly_hours": staff.weekly_hours,
        "consecutive_periods": staff.consecutive_periods,
        "students_per_batch": staff.students_per_batch
    }
    return store.lab_staffing_requirements[req_id]

@router.get("/lab-batches", response_model=List[LabBatchSchema])
async def list_lab_batches(section_id: Optional[str] = None):
    if section_id:
        return [b for b in store.lab_batches.values() if b["section_id"] == section_id]
    return list(store.lab_batches.values())

@router.post("/lab-batches", response_model=LabBatchSchema)
async def create_lab_batch(batch: LabBatchSchema, user: dict = Depends(require_officer)):
    b_id = batch.id or str(uuid.uuid4())
    store.lab_batches[b_id] = {
        "id": b_id,
        "section_id": batch.section_id,
        "batch_name": batch.batch_name,
        "student_count": batch.student_count
    }
    return store.lab_batches[b_id]

# 9. PROFESSIONAL ELECTIVES
@router.get("/electives")
async def list_electives():
    res = []
    for grp in store.elective_groups.values():
        g_copy = grp.copy()
        g_copy["options"] = [
            opt for opt in store.elective_options.values() if opt.get("elective_group_id") == grp["id"]
        ]
        res.append(g_copy)
    return res

# 10. TIME SLOTS & AVAILABILITY
@router.get("/time-slots", response_model=List[TimeSlotSchema])
async def list_time_slots():
    slots = list(store.time_slots.values())
    slots.sort(key=lambda s: (s["day_of_week"], s["period_number"]))
    return slots

@router.get("/availability")
async def get_availability():
    return {
        "faculty": store.faculty_availability,
        "sections": store.section_availability,
        "classrooms": store.classroom_availability,
        "laboratories": store.lab_availability
    }

@router.post("/availability")
async def update_availability(payload: Dict[str, Any], user: dict = Depends(require_officer)):
    category = payload.get("category") # faculty, section, classroom, laboratory
    entity_id = payload.get("entity_id")
    slot_id = payload.get("slot_id")
    is_available = payload.get("is_available", True)

    key = f"{entity_id}_{slot_id}"
    if category == "faculty":
        store.faculty_availability[key] = is_available
    elif category == "section":
        store.section_availability[key] = is_available
    elif category == "classroom":
        store.classroom_availability[key] = is_available
    elif category == "laboratory":
        store.lab_availability[key] = is_available
    else:
        raise HTTPException(status_code=400, detail="Invalid availability category")

    return {"status": "success", "updated": key, "is_available": is_available}
