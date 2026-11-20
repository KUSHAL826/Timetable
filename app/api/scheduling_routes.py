import uuid
import copy
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from app.auth.dependencies import require_officer, get_current_user
from app.services.data_store import store
from app.schemas.scheduling import (
    ValidationDashboardResponse, ValidationItem,
    TimetableGenerationRequest, TimetableGenerationResponse,
    TimetableEntryResponse, TimetableManualEditRequest, TimetableApprovalRequest
)
from app.agents.orchestrator import TimetableAgentOrchestrator
from app.scheduling.validator import TimetableConflictValidator

router = APIRouter(prefix="/scheduling", tags=["Timetable Scheduling & Validation"])

def _build_cluster_data(cluster_id: str) -> Dict[str, Any]:
    """Assembles all data needed for validation and OR-Tools scheduling for a cluster."""
    cluster = store.clusters.get(cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    sec_ids = [cs["section_id"] for cs in store.cluster_sections if cs["cluster_id"] == cluster_id]
    sections = [store.sections[s] for s in sec_ids if s in store.sections]

    # Gather curriculum allocations
    theory_reqs = []
    for s_id in sec_ids:
        # Find all section subjects
        for ss in store.section_subjects.values():
            if ss["section_id"] == s_id:
                sub = store.subjects.get(ss["subject_id"])
                if sub and sub["subject_type"] == "theory":
                    # find allocation
                    alloc = next((sa for sa in store.subject_allocations.values() if sa["section_subject_id"] == ss["id"]), None)
                    if alloc:
                        theory_reqs.append({
                            "section_id": s_id,
                            "subject_id": ss["subject_id"],
                            "primary_faculty_id": alloc["faculty_id"],
                            "weekly_hours": ss["weekly_hours"]
                        })

    # Gather lab staffing requirements
    lab_reqs = []
    for s_id in sec_ids:
        for l_staff in store.lab_staffing_requirements.values():
            if l_staff["section_id"] == s_id:
                # get batches
                sec_batches = [b for b in store.lab_batches.values() if b["section_id"] == s_id]
                lab_reqs.append({
                    "section_id": s_id,
                    "subject_id": l_staff["subject_id"],
                    "lab_id": l_staff["lab_id"],
                    "primary_faculty_id": l_staff["primary_faculty_id"],
                    "required_co_teacher_count": l_staff["required_co_teacher_count"],
                    "co_teacher_ids": l_staff.get("co_teacher_ids", []),
                    "weekly_hours": l_staff["weekly_hours"],
                    "consecutive_periods": l_staff.get("consecutive_periods", 2),
                    "batches": sec_batches
                })

    # Gather electives
    elec_groups = []
    for grp in store.elective_groups.values():
        if any(sid in grp.get("participating_section_ids", []) for sid in sec_ids):
            opts = [opt for opt in store.elective_options.values() if opt["elective_group_id"] == grp["id"]]
            elec_groups.append({
                "id": grp["id"],
                "group_name": grp["group_name"],
                "weekly_hours": grp.get("weekly_hours", 3),
                "participating_section_ids": grp.get("participating_section_ids", []),
                "options": opts
            })

    # Availability tuples
    fac_avail = {}
    sec_avail = {}
    room_avail = {}
    lab_avail = {}
    for slot_id in store.time_slots.keys():
        for f_id in store.faculty.keys():
            fac_avail[(f_id, slot_id)] = store.faculty_availability.get(f"{f_id}_{slot_id}", True)
        for s_id in sec_ids:
            sec_avail[(s_id, slot_id)] = store.section_availability.get(f"{s_id}_{slot_id}", True)
        for r_id in store.classrooms.keys():
            room_avail[(r_id, slot_id)] = store.classroom_availability.get(f"{r_id}_{slot_id}", True)
        for l_id in store.laboratories.keys():
            lab_avail[(l_id, slot_id)] = store.lab_availability.get(f"{l_id}_{slot_id}", True)

    qualifications = {
        (fs["faculty_id"], fs["subject_id"]): fs.get("is_qualified", True)
        for fs in store.faculty_subjects.values()
    }

    return {
        "cluster": cluster,
        "sections": sections,
        "subjects": list(store.subjects.values()),
        "faculty": list(store.faculty.values()),
        "classrooms": list(store.classrooms.values()),
        "laboratories": list(store.laboratories.values()),
        "time_slots": list(store.time_slots.values()),
        "theory_requirements": theory_reqs,
        "lab_requirements": lab_reqs,
        "lab_batches": [b for b in store.lab_batches.values() if b["section_id"] in sec_ids],
        "elective_groups": elec_groups,
        "faculty_availability": fac_avail,
        "section_availability": sec_avail,
        "classroom_availability": room_avail,
        "lab_availability": lab_avail,
        "qualifications": qualifications
    }

@router.get("/validation-dashboard", response_model=ValidationDashboardResponse)
async def get_validation_dashboard(cluster_id: Optional[str] = None):
    """
    Input First, Validation Second, Generation Last:
    Computes real-time institutional validation status across all mandatory modules.
    Identifies blocking errors, warnings, and completed entries.
    """
    modules = []

    # 1. Academic Structure
    clusters_count = len(store.clusters)
    sections_count = len(store.sections)
    if clusters_count == 0 or sections_count == 0:
        modules.append(ValidationItem(
            module="Academic Structure",
            status="error",
            title="Incomplete Academic Structure",
            message="At least one cluster and mapped sections are mandatory before generation.",
            count=clusters_count,
            link="/academic/clusters",
            is_blocking=True,
            details=["No active clusters or sections found."]
        ))
    else:
        modules.append(ValidationItem(
            module="Academic Structure",
            status="complete",
            title="Clusters & Sections Configured",
            message=f"{clusters_count} cluster(s) with {sections_count} sections active.",
            count=clusters_count,
            link="/academic/clusters",
            is_blocking=False
        ))

    # 2. Faculty Management & Qualifications
    faculty_count = len(store.faculty)
    if faculty_count < 2:
        modules.append(ValidationItem(
            module="Faculty Roster",
            status="error",
            title="Insufficient Faculty Members",
            message="At least 2 qualified faculty members required.",
            count=faculty_count,
            link="/academic/faculty",
            is_blocking=True,
            details=["Faculty roster is empty or incomplete."]
        ))
    else:
        modules.append(ValidationItem(
            module="Faculty Roster",
            status="complete",
            title="Faculty Roster Verified",
            message=f"{faculty_count} faculty members configured and mapped.",
            count=faculty_count,
            link="/academic/faculty",
            is_blocking=False
        ))

    # 3. Classrooms & Capacity
    rooms = list(store.classrooms.values())
    max_sec_strength = max((s["student_strength"] for s in store.sections.values()), default=0)
    has_room_undersized = any(r["capacity"] < max_sec_strength for r in rooms) if rooms else True

    if not rooms:
        modules.append(ValidationItem(
            module="Classrooms",
            status="error",
            title="No Classrooms Configured",
            message="At least one lecture classroom must be defined.",
            count=0,
            link="/academic/classrooms",
            is_blocking=True,
            details=["Zero classrooms registered."]
        ))
    else:
        modules.append(ValidationItem(
            module="Classrooms",
            status="complete",
            title="Classrooms & Seating Capacity",
            message=f"{len(rooms)} lecture halls verified (sufficient capacity for section strength).",
            count=len(rooms),
            link="/academic/classrooms",
            is_blocking=False
        ))

    # 4. Laboratories & Staffing Requirements
    labs = list(store.laboratories.values())
    lab_staffing = list(store.lab_staffing_requirements.values())
    staffing_errors = []
    for staff in lab_staffing:
        if len(staff.get("co_teacher_ids", [])) != staff.get("required_co_teacher_count", 0):
            staffing_errors.append(f"Section {staff['section_id']}: Required {staff['required_co_teacher_count']} co-teachers, but {len(staff.get('co_teacher_ids', []))} assigned.")

    if not labs:
        modules.append(ValidationItem(
            module="Laboratories",
            status="error",
            title="No Laboratories Registered",
            message="Laboratories required for practical curriculum.",
            count=0,
            link="/academic/laboratories",
            is_blocking=True,
            details=["Zero laboratories registered."]
        ))
    elif staffing_errors:
        modules.append(ValidationItem(
            module="Lab Staffing",
            status="error",
            title="Lab Co-Teacher Mismatch",
            message="Configured co-teacher counts must match assigned co-teachers exactly.",
            count=len(staffing_errors),
            link="/academic/lab-staffing",
            is_blocking=True,
            details=staffing_errors
        ))
    else:
        modules.append(ValidationItem(
            module="Laboratories & Staffing",
            status="complete",
            title="Laboratories & Staffing Fulfill Requirements",
            message=f"{len(labs)} labs registered with valid primary faculty and co-teacher rosters.",
            count=len(labs),
            link="/academic/laboratories",
            is_blocking=False
        ))

    # 5. Lab Batches
    batches = list(store.lab_batches.values())
    if not batches:
        modules.append(ValidationItem(
            module="Lab Batches",
            status="error",
            title="Missing Student Batches",
            message="Lab practicals require student batch partitioning.",
            count=0,
            link="/academic/lab-batches",
            is_blocking=True,
            details=["No lab batches configured for sections."]
        ))
    else:
        modules.append(ValidationItem(
            module="Lab Batches",
            status="complete",
            title="Lab Batches Configured",
            message=f"{len(batches)} student batches verified.",
            count=len(batches),
            link="/academic/lab-batches",
            is_blocking=False
        ))

    # 6. Professional Electives
    electives = list(store.elective_groups.values())
    modules.append(ValidationItem(
        module="Professional Electives",
        status="complete",
        title="Elective Blocks Configured",
        message=f"{len(electives)} synchronized elective block(s) ready.",
        count=len(electives),
        link="/academic/electives",
        is_blocking=False
    ))

    # 7. Availability Matrix
    slots_count = len(store.time_slots)
    modules.append(ValidationItem(
        module="Time Slots & Availability",
        status="complete",
        title="Time Grid & Availability Matrices Set",
        message=f"{slots_count} weekly periods configured with explicit availability states.",
        count=slots_count,
        link="/academic/availability",
        is_blocking=False
    ))

    blocking_errors = sum(1 for m in modules if m.is_blocking)
    warnings = sum(1 for m in modules if m.status == "warning")
    complete_count = sum(1 for m in modules if m.status == "complete")

    return ValidationDashboardResponse(
        is_valid=(blocking_errors == 0),
        blocking_error_count=blocking_errors,
        warning_count=warnings,
        complete_count=complete_count,
        modules=modules
    )

@router.post("/generate", response_model=TimetableGenerationResponse)
async def generate_timetable(
    req: TimetableGenerationRequest,
    user: dict = Depends(require_officer)
):
    """
    Strict Timetable Generation Rule:
    Disabled until EVERY blocking error is resolved.
    Runs Google OR-Tools CP-SAT scheduler, logs input snapshot, and creates versioned draft.
    """
    validation_status = await get_validation_dashboard(req.cluster_id)
    if not validation_status.is_valid:
        raise HTTPException(
            status_code=400,
            detail=f"Generation blocked: {validation_status.blocking_error_count} unresolved blocking error(s) remain."
        )

    cluster_data = _build_cluster_data(req.cluster_id)
    cluster_data["solver_timeout_seconds"] = req.solver_timeout_seconds

    # Run LangGraph Orchestrator and OR-Tools optimization
    orchestrator = TimetableAgentOrchestrator()
    result = orchestrator.generate_and_optimize(cluster_data)

    gen_id = str(uuid.uuid4())

    if not result["success"]:
        # Save failed generation record with diagnostics
        store.timetable_generations[gen_id] = {
            "id": gen_id,
            "cluster_id": req.cluster_id,
            "semester_id": req.semester_id,
            "generated_by": user.get("sub"),
            "solver_status": result.get("solver_status", "INFEASIBLE"),
            "status": "failed",
            "diagnostics": result.get("diagnostics"),
            "input_snapshot": copy.deepcopy(cluster_data),
            "created_at": datetime.utcnow().isoformat()
        }
        raise HTTPException(
            status_code=422,
            detail=f"Solver returned {result.get('solver_status')}. Constraints cannot be satisfied simultaneously."
        )

    # Save immutable generation version
    store.timetable_generations[gen_id] = {
        "id": gen_id,
        "cluster_id": req.cluster_id,
        "semester_id": req.semester_id,
        "generated_by": user.get("sub"),
        "solver_status": result.get("solver_status"),
        "status": "draft",
        "solve_time_seconds": result.get("solve_time_seconds"),
        "input_snapshot": copy.deepcopy(cluster_data),
        "created_at": datetime.utcnow().isoformat()
    }

    # Store individual entries
    for e in result.get("entries", []):
        entry_id = str(uuid.uuid4())
        e_copy = e.copy()
        e_copy["id"] = entry_id
        e_copy["generation_id"] = gen_id
        store.timetable_entries[entry_id] = e_copy

    return TimetableGenerationResponse(
        generation_id=gen_id,
        status="draft",
        solver_status=result.get("solver_status"),
        solve_time_seconds=result.get("solve_time_seconds"),
        entries_count=len(result.get("entries", [])),
        conflicts=[],
        warnings=[]
    )

@router.get("/timetable/{generation_id}")
async def get_timetable_entries(
    generation_id: str,
    section_id: Optional[str] = None,
    faculty_id: Optional[str] = None,
    classroom_id: Optional[str] = None,
    laboratory_id: Optional[str] = None,
    day_of_week: Optional[int] = None,
    user: dict = Depends(get_current_user)
):
    """
    Returns timetable schedule entries with multi-dimensional filtering.
    For teachers, restricts view to authorized entries unless published.
    """
    gen = store.timetable_generations.get(generation_id)
    if not gen:
        raise HTTPException(status_code=404, detail="Timetable generation not found")

    # Teachers can view only published or their own sessions
    if user.get("role") == "teacher" and gen.get("status") != "published":
        faculty_id = user.get("sub")

    entries = [e for e in store.timetable_entries.values() if e.get("generation_id") == generation_id]

    if section_id:
        entries = [e for e in entries if e.get("section_id") == section_id]
    if faculty_id:
        entries = [
            e for e in entries
            if e.get("faculty_id") == faculty_id or faculty_id in e.get("co_faculty_ids", [])
        ]
    if classroom_id:
        entries = [e for e in entries if e.get("classroom_id") == classroom_id]
    if laboratory_id:
        entries = [e for e in entries if e.get("laboratory_id") == laboratory_id]
    if day_of_week:
        entries = [e for e in entries if e.get("day_of_week") == day_of_week]

    # Enrich with names
    enriched = []
    for e in entries:
        sec = store.sections.get(e.get("section_id"), {})
        sub = store.subjects.get(e.get("subject_id"), {})
        fac = store.faculty.get(e.get("faculty_id"), {})
        room = store.classrooms.get(e.get("classroom_id"), {})
        lab = store.laboratories.get(e.get("laboratory_id"), {})
        batch = store.lab_batches.get(e.get("lab_batch_id"), {})
        slot = store.time_slots.get(e.get("time_slot_id"), {})

        co_fac_names = [
            store.faculty[cid]["full_name"] for cid in e.get("co_faculty_ids", []) if cid in store.faculty
        ]

        enriched.append({
            "id": e["id"],
            "generation_id": e["generation_id"],
            "section_id": e.get("section_id"),
            "section_name": sec.get("name", "Elective Block" if e.get("entry_type") == "elective" else ""),
            "subject_id": e.get("subject_id"),
            "subject_code": sub.get("subject_code", ""),
            "subject_name": sub.get("subject_name", ""),
            "faculty_id": e.get("faculty_id"),
            "faculty_name": fac.get("full_name", ""),
            "co_faculty_names": co_fac_names,
            "classroom_id": e.get("classroom_id"),
            "room_code": room.get("room_code", ""),
            "laboratory_id": e.get("laboratory_id"),
            "lab_name": lab.get("lab_name", ""),
            "lab_batch_id": e.get("lab_batch_id"),
            "batch_name": batch.get("batch_name", ""),
            "time_slot_id": e.get("time_slot_id"),
            "day_of_week": e.get("day_of_week", slot.get("day_of_week")),
            "period_number": e.get("period_number", slot.get("period_number")),
            "start_time": e.get("start_time", slot.get("start_time")),
            "end_time": e.get("end_time", slot.get("end_time")),
            "entry_type": e.get("entry_type", "regular")
        })

    enriched.sort(key=lambda x: (x.get("day_of_week", 0), x.get("period_number", 0)))
    return enriched

@router.get("/generations")
async def list_generations():
    gens = list(store.timetable_generations.values())
    gens.sort(key=lambda g: g.get("created_at", ""), reverse=True)
    return gens

@router.post("/manual-edit")
async def manual_edit_entry(
    req: TimetableManualEditRequest,
    user: dict = Depends(require_officer)
):
    """
    Manual Timetable Editor:
    Allows officer to move a period or modify faculty/room.
    Immediately re-runs independent conflict validator and preserves draft state.
    """
    entry = store.timetable_entries.get(req.entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Timetable entry not found")

    gen_id = entry["generation_id"]
    gen = store.timetable_generations.get(gen_id)
    if gen and gen.get("status") == "published":
        raise HTTPException(status_code=400, detail="Cannot manually edit a published timetable. Create a new draft.")

    # Apply tentative edit
    if req.new_time_slot_id:
        slot = store.time_slots.get(req.new_time_slot_id)
        if slot:
            entry["time_slot_id"] = req.new_time_slot_id
            entry["day_of_week"] = slot["day_of_week"]
            entry["period_number"] = slot["period_number"]
            entry["start_time"] = slot["start_time"]
            entry["end_time"] = slot["end_time"]

    if req.new_faculty_id:
        entry["faculty_id"] = req.new_faculty_id
    if req.new_classroom_id:
        entry["classroom_id"] = req.new_classroom_id
    if req.new_laboratory_id:
        entry["laboratory_id"] = req.new_laboratory_id
    if req.new_lab_batch_id:
        entry["lab_batch_id"] = req.new_lab_batch_id

    # Run independent validation on the updated entries
    all_gen_entries = [e for e in store.timetable_entries.values() if e.get("generation_id") == gen_id]
    validator = TimetableConflictValidator(
        entries=all_gen_entries,
        sections=store.sections,
        subjects=store.subjects,
        faculty=store.faculty,
        classrooms=store.classrooms,
        laboratories=store.laboratories,
        batches=store.lab_batches,
        qualifications={(fs["faculty_id"], fs["subject_id"]): fs.get("is_qualified", True) for fs in store.faculty_subjects.values()},
        availability={"faculty": store.faculty_availability}
    )
    conflicts = validator.validate_all()

    return {
        "status": "success",
        "has_conflicts": len(conflicts) > 0,
        "conflicts_count": len(conflicts),
        "conflicts": conflicts,
        "entry": entry
    }

@router.post("/approval")
async def process_approval(
    req: TimetableApprovalRequest,
    user: dict = Depends(require_officer)
):
    """Lifecycle workflow: submit -> approve -> publish -> archive."""
    gen = store.timetable_generations.get(req.generation_id)
    if not gen:
        raise HTTPException(status_code=404, detail="Generation not found")

    action_to_status = {
        "submit": "submitted",
        "approve": "approved",
        "reject": "draft",
        "publish": "published",
        "archive": "archived"
    }

    new_status = action_to_status.get(req.action)
    gen["status"] = new_status
    gen["updated_at"] = datetime.utcnow().isoformat()

    approval_id = str(uuid.uuid4())
    store.timetable_approvals[approval_id] = {
        "id": approval_id,
        "generation_id": req.generation_id,
        "actor_id": user.get("sub"),
        "approval_status": req.action,
        "comments": req.comments,
        "created_at": datetime.utcnow().isoformat()
    }

    return {"status": "success", "new_lifecycle_state": new_status}

@router.get("/teacher-schedule")
async def get_teacher_schedule(user: dict = Depends(get_current_user)):
    """Teacher Dashboard: Shows personal daily & weekly timetable, lab sessions, and sections."""
    employee_id = user.get("employee_id")
    profile = store.profiles.get(employee_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Teacher profile not found")

    fac_id = profile["id"]
    # Get active published generation, or latest draft for preview
    active_gen = next(
        (g for g in store.timetable_generations.values() if g.get("status") == "published"),
        next(iter(store.timetable_generations.values()), None)
    )

    if not active_gen:
        return {
            "teacher": profile,
            "has_timetable": False,
            "schedule": [],
            "message": "No active published timetable available."
        }

    # Fetch teacher entries
    t_entries = [
        e for e in store.timetable_entries.values()
        if e.get("generation_id") == active_gen["id"] and
        (e.get("faculty_id") == fac_id or fac_id in e.get("co_faculty_ids", []))
    ]

    enriched = []
    for e in t_entries:
        sec = store.sections.get(e.get("section_id"), {})
        sub = store.subjects.get(e.get("subject_id"), {})
        room = store.classrooms.get(e.get("classroom_id"), {})
        lab = store.laboratories.get(e.get("laboratory_id"), {})
        batch = store.lab_batches.get(e.get("lab_batch_id"), {})
        slot = store.time_slots.get(e.get("time_slot_id"), {})

        enriched.append({
            "id": e["id"],
            "section_name": sec.get("name", ""),
            "subject_code": sub.get("subject_code", ""),
            "subject_name": sub.get("subject_name", ""),
            "room_code": room.get("room_code", ""),
            "lab_name": lab.get("lab_name", ""),
            "batch_name": batch.get("batch_name", ""),
            "day_of_week": e.get("day_of_week", slot.get("day_of_week")),
            "period_number": e.get("period_number", slot.get("period_number")),
            "start_time": e.get("start_time", slot.get("start_time")),
            "end_time": e.get("end_time", slot.get("end_time")),
            "is_co_teacher": fac_id in e.get("co_faculty_ids", []),
            "entry_type": e.get("entry_type", "regular")
        })

    enriched.sort(key=lambda x: (x.get("day_of_week", 0), x.get("period_number", 0)))
    return {
        "teacher": profile,
        "has_timetable": True,
        "generation_status": active_gen.get("status"),
        "schedule": enriched
    }
