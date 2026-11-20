import os
import uuid
import copy
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.services.data_store import store
from app.auth.security import verify_password, get_password_hash, create_access_token, decode_access_token
from app.agents.orchestrator import TimetableAgentOrchestrator
from app.scheduling.validator import TimetableConflictValidator

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory="app/templates")

def render_template(request: Request, name: str, context: Optional[dict] = None) -> HTMLResponse:
    ctx = context.copy() if context else {}
    return templates.TemplateResponse(request=request, name=name, context=ctx)

def get_current_web_user(request: Request) -> Optional[dict]:
    token = request.cookies.get("smarttimetable_token")
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    emp_id = payload.get("employee_id")
    return store.profiles.get(emp_id)

@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    user = get_current_web_user(request)
    if user:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    user = get_current_web_user(request)
    if user:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    return render_template(request, "login.html", {
        "request": request,
        "must_change_password": False
    })

@router.post("/login", response_class=HTMLResponse)
async def handle_login(
    request: Request,
    employee_id: str = Form(...),
    password: str = Form(...)
):
    emp_id = employee_id.strip()
    profile = store.profiles.get(emp_id)

    if not profile or not profile.get("is_active", True):
        return render_template(request, "login.html", {
            "request": request,
            "error": "Invalid Teacher ID / Officer ID or account inactive.",
            "must_change_password": False
        })

    if not verify_password(password, profile["password_hash"]):
        return render_template(request, "login.html", {
            "request": request,
            "error": "Invalid password provided.",
            "must_change_password": False
        })

    # Check if must change password on initial login
    if profile.get("must_change_password", False):
        return render_template(request, "login.html", {
            "request": request,
            "must_change_password": True,
            "temp_employee_id": emp_id,
            "temp_old_password": password
        })

    # Issue token and set in cookie
    token_payload = {
        "sub": profile["id"],
        "employee_id": profile["employee_id"],
        "role": profile["role"],
        "full_name": profile["full_name"],
        "must_change_password": False
    }
    token = create_access_token(token_payload)

    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    response.set_cookie(key="smarttimetable_token", value=token, httponly=True)
    return response

@router.post("/change-password-first", response_class=HTMLResponse)
async def handle_first_password_change(
    request: Request,
    employee_id: str = Form(...),
    old_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...)
):
    emp_id = employee_id.strip()
    profile = store.profiles.get(emp_id)
    if not profile:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    if new_password != confirm_password:
        return render_template(request, "login.html", {
            "request": request,
            "must_change_password": True,
            "temp_employee_id": emp_id,
            "temp_old_password": old_password,
            "error": "New password and confirmation do not match."
        })

    if len(new_password) < 8:
        return render_template(request, "login.html", {
            "request": request,
            "must_change_password": True,
            "temp_employee_id": emp_id,
            "temp_old_password": old_password,
            "error": "Password must be at least 8 characters long."
        })

    if new_password == old_password:
        return render_template(request, "login.html", {
            "request": request,
            "must_change_password": True,
            "temp_employee_id": emp_id,
            "temp_old_password": old_password,
            "error": "New password cannot match your temporary password."
        })

    # Update password
    profile["password_hash"] = get_password_hash(new_password)
    profile["must_change_password"] = False

    # Issue session token
    token = create_access_token({
        "sub": profile["id"],
        "employee_id": profile["employee_id"],
        "role": profile["role"],
        "full_name": profile["full_name"],
        "must_change_password": False
    })

    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    response.set_cookie(key="smarttimetable_token", value=token, httponly=True)
    return response

@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key="smarttimetable_token")
    return response

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = get_current_web_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    # 1. Timetable Officer Dashboard
    if user.get("role") == "timetable_officer":
        from app.api.scheduling_routes import get_validation_dashboard
        val_data = await get_validation_dashboard()
        gens = []
        for g in store.timetable_generations.values():
            g_copy = g.copy()
            c = store.clusters.get(g.get("cluster_id"), {})
            d = store.get_department(c.get("department_id"))
            g_copy["cluster_name"] = c.get("name", "College Cluster")
            g_copy["department_name"] = d.get("name", "Multi-Department")
            gens.append(g_copy)
        gens.sort(key=lambda g: g.get("created_at", ""), reverse=True)

        return render_template(request, "officer_dashboard.html", {
            "request": request,
            "current_user": user,
            "active_page": "dashboard",
            "stats": {
                "clusters": len(store.clusters),
                "sections": len(store.sections),
                "faculty": len(store.faculty),
                "subjects": len(store.subjects),
                "classrooms": len(store.classrooms),
                "laboratories": len(store.laboratories)
            },
            "validation": val_data,
            "is_blocked": val_data.blocking_error_count > 0,
            "generations": gens
        })

    # 2. Teacher Portal Dashboard (Strictly Read-Only, No Edits, Dynamic Department)
    else:
        # Find teacher's dynamic department
        fac = next((f for f in store.faculty.values() if f.get("employee_id") == user["employee_id"]), None)
        teacher_dept = store.get_department(fac.get("department_id")) if fac else None
        teacher_dept_name = teacher_dept.get("name", "College Faculty") if teacher_dept else "College Faculty"
        teacher_dept_code = teacher_dept.get("code", "") if teacher_dept else ""

        active_gen = next(
            (g for g in store.timetable_generations.values() if g.get("status") == "published"),
            next(iter(store.timetable_generations.values()), None)
        )
        schedule = []
        if active_gen and fac:
            fac_id = fac["id"]
            t_entries = [
                e for e in store.timetable_entries.values()
                if e.get("generation_id") == active_gen["id"] and
                (e.get("faculty_id") == fac_id or fac_id in e.get("co_faculty_ids", []))
            ]
            for e in t_entries:
                sec = store.sections.get(e.get("section_id"), {})
                sub = store.subjects.get(e.get("subject_id"), {})
                room = store.classrooms.get(e.get("classroom_id"), {})
                lab = store.laboratories.get(e.get("laboratory_id"), {})
                batch = store.lab_batches.get(e.get("lab_batch_id"), {})
                slot = store.time_slots.get(e.get("time_slot_id"), {})
                schedule.append({
                    "day_of_week": e.get("day_of_week", slot.get("day_of_week")),
                    "period_number": e.get("period_number", slot.get("period_number")),
                    "start_time": e.get("start_time", slot.get("start_time")),
                    "end_time": e.get("end_time", slot.get("end_time")),
                    "section_name": sec.get("name", ""),
                    "subject_code": sub.get("subject_code", ""),
                    "subject_name": sub.get("subject_name", ""),
                    "room_code": room.get("room_code", ""),
                    "lab_name": lab.get("lab_name", ""),
                    "batch_name": batch.get("batch_name", ""),
                    "is_co_teacher": fac_id in e.get("co_faculty_ids", []),
                    "entry_type": e.get("entry_type", "regular")
                })

        day_names = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday"}
        schedule_by_day = {d: [] for d in [1, 2, 3, 4, 5]}
        for s in schedule:
            d = s.get("day_of_week")
            if d in schedule_by_day:
                schedule_by_day[d].append(s)

        return render_template(request, "teacher_dashboard.html", {
            "request": request,
            "current_user": user,
            "active_page": "dashboard",
            "teacher_department_name": teacher_dept_name,
            "teacher_department_code": teacher_dept_code,
            "has_timetable": bool(active_gen),
            "generation_status": active_gen.get("status", "draft") if active_gen else "pending",
            "schedule": schedule,
            "schedule_by_day": schedule_by_day,
            "day_names": day_names
        })

@router.get("/faculty", response_class=HTMLResponse)
async def faculty_management(request: Request):
    user = get_current_web_user(request)
    if not user or user.get("role") != "timetable_officer":
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

    faculty_list = []
    for f in store.faculty.values():
        qual_subs = [
            store.subjects[fs["subject_id"]]["subject_code"]
            for fs in store.faculty_subjects.values()
            if fs["faculty_id"] == f["id"] and fs.get("is_qualified", True) and fs["subject_id"] in store.subjects
        ]
        dept = store.get_department(f.get("department_id"))
        f_copy = f.copy()
        f_copy["qualified_subjects"] = qual_subs
        f_copy["department_name"] = dept.get("name", "General Department")
        f_copy["department_code"] = dept.get("code", "GEN")
        faculty_list.append(f_copy)

    return render_template(request, "faculty.html", {
        "request": request,
        "current_user": user,
        "active_page": "faculty",
        "faculty": faculty_list,
        "departments": list(store.departments.values()),
        "success_created": None
    })

@router.post("/faculty/create", response_class=HTMLResponse)
async def create_faculty_member(
    request: Request,
    employee_id: str = Form(...),
    full_name: str = Form(...),
    department_id: str = Form(...),
    phone_number: str = Form(...),
    max_weekly_hours: int = Form(20),
    email: Optional[str] = Form(None)
):
    user = get_current_web_user(request)
    if not user or user.get("role") != "timetable_officer":
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

    emp_id = employee_id.strip()
    fac_id = str(uuid.uuid4())

    # 1. Save Faculty Record with explicit dynamic department
    store.faculty[fac_id] = {
        "id": fac_id,
        "employee_id": emp_id,
        "full_name": full_name.strip(),
        "department_id": department_id,
        "phone_number": phone_number.strip(),
        "email": email or f"{emp_id.lower()}@college.edu",
        "max_weekly_hours": max_weekly_hours,
        "is_active": True,
        "created_at": datetime.utcnow().isoformat()
    }

    # 2. Save Teacher Auth Profile with initial password = phone_number
    store.profiles[emp_id] = {
        "id": fac_id,
        "employee_id": emp_id,
        "full_name": full_name.strip(),
        "role": "teacher",
        "phone_number": phone_number.strip(),
        "password_hash": get_password_hash(phone_number.strip()),
        "must_change_password": True,
        "is_active": True,
        "created_at": datetime.utcnow().isoformat()
    }

    # Qualify for subjects in their department by default
    for sub_id, sub in store.subjects.items():
        if not sub.get("department_id") or sub.get("department_id") == department_id:
            store.faculty_subjects[f"{fac_id}_{sub_id}"] = {
                "faculty_id": fac_id,
                "subject_id": sub_id,
                "is_qualified": True
            }

    # Initialize availability
    for s_id in store.time_slots.keys():
        store.faculty_availability[f"{fac_id}_{s_id}"] = True

    dept = store.get_department(department_id)

    faculty_list = []
    for f in store.faculty.values():
        qual_subs = [
            store.subjects[fs["subject_id"]]["subject_code"]
            for fs in store.faculty_subjects.values()
            if fs["faculty_id"] == f["id"] and fs.get("is_qualified", True) and fs["subject_id"] in store.subjects
        ]
        f_dept = store.get_department(f.get("department_id"))
        f_copy = f.copy()
        f_copy["qualified_subjects"] = qual_subs
        f_copy["department_name"] = f_dept.get("name", "General Department")
        f_copy["department_code"] = f_dept.get("code", "GEN")
        faculty_list.append(f_copy)

    return render_template(request, "faculty.html", {
        "request": request,
        "current_user": user,
        "active_page": "faculty",
        "faculty": faculty_list,
        "departments": list(store.departments.values()),
        "success_created": {
            "employee_id": emp_id,
            "full_name": full_name.strip(),
            "department_name": dept.get("name", "College Department"),
            "phone_number": phone_number.strip()
        }
    })

@router.post("/faculty/edit", response_class=HTMLResponse)
async def edit_faculty_member(
    request: Request,
    faculty_id: str = Form(...),
    full_name: str = Form(...),
    department_id: str = Form(...),
    phone_number: str = Form(...),
    max_weekly_hours: int = Form(20),
    email: Optional[str] = Form(None)
):
    user = get_current_web_user(request)
    if not user or user.get("role") != "timetable_officer":
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

    fac = store.faculty.get(faculty_id)
    if fac:
        fac["full_name"] = full_name.strip()
        fac["department_id"] = department_id
        fac["phone_number"] = phone_number.strip()
        fac["email"] = email or fac.get("email", "")
        fac["max_weekly_hours"] = max_weekly_hours

        # Synchronize profile display details
        emp_id = fac.get("employee_id")
        if emp_id and emp_id in store.profiles:
            store.profiles[emp_id]["full_name"] = full_name.strip()
            store.profiles[emp_id]["phone_number"] = phone_number.strip()

    return RedirectResponse(url="/faculty", status_code=status.HTTP_302_FOUND)

@router.post("/faculty/delete", response_class=HTMLResponse)
async def delete_faculty_member(
    request: Request,
    faculty_id: str = Form(...)
):
    user = get_current_web_user(request)
    if not user or user.get("role") != "timetable_officer":
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

    store.delete_faculty(faculty_id)
    return RedirectResponse(url="/faculty", status_code=status.HTTP_302_FOUND)

@router.get("/subjects", response_class=HTMLResponse)
async def subjects_page(request: Request):
    user = get_current_web_user(request)
    if not user or user.get("role") != "timetable_officer":
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

    sub_list = []
    theory_count = 0
    lab_count = 0
    total_credits = 0

    for s in store.subjects.values():
        s_copy = s.copy()
        dept = store.get_department(s.get("department_id"))
        s_copy["department_name"] = dept.get("name", "General Department")
        s_copy["department_code"] = dept.get("code", "GEN")
        sub_list.append(s_copy)

        if s.get("subject_type") == "practical":
            lab_count += 1
        else:
            theory_count += 1
        total_credits += int(s.get("credits", 0))

    sub_list.sort(key=lambda x: x.get("subject_code", ""))

    return render_template(request, "subjects.html", {
        "request": request,
        "current_user": user,
        "active_page": "subjects",
        "subjects": sub_list,
        "departments": list(store.departments.values()),
        "stats": {
            "theory_count": theory_count,
            "lab_count": lab_count,
            "total_credits": total_credits
        }
    })

@router.post("/subjects/create", response_class=HTMLResponse)
async def create_subject_entry(
    request: Request,
    subject_code: str = Form(...),
    subject_name: str = Form(...),
    subject_type: str = Form("theory"),
    department_id: str = Form(...),
    weekly_hours: int = Form(4),
    consecutive_periods: int = Form(1),
    credits: int = Form(4)
):
    user = get_current_web_user(request)
    if not user or user.get("role") != "timetable_officer":
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

    sub_id = str(uuid.uuid4())
    sem_id = next(iter(store.semesters.keys()), "s5555555-5555-5555-5555-555555555555")
    store.subjects[sub_id] = {
        "id": sub_id,
        "subject_code": subject_code.strip().upper(),
        "subject_name": subject_name.strip(),
        "subject_type": subject_type.strip(),
        "weekly_hours": weekly_hours,
        "consecutive_periods": consecutive_periods,
        "department_id": department_id,
        "credits": credits,
        "semester_id": sem_id,
        "is_active": True
    }
    return RedirectResponse(url="/subjects", status_code=status.HTTP_302_FOUND)

@router.post("/subjects/edit", response_class=HTMLResponse)
async def edit_subject_entry(
    request: Request,
    subject_id: str = Form(...),
    subject_code: str = Form(...),
    subject_name: str = Form(...),
    subject_type: str = Form("theory"),
    department_id: str = Form(...),
    weekly_hours: int = Form(4),
    consecutive_periods: int = Form(1),
    credits: int = Form(4)
):
    user = get_current_web_user(request)
    if not user or user.get("role") != "timetable_officer":
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

    sub = store.subjects.get(subject_id)
    if sub:
        sub["subject_code"] = subject_code.strip().upper()
        sub["subject_name"] = subject_name.strip()
        sub["subject_type"] = subject_type.strip()
        sub["department_id"] = department_id
        sub["weekly_hours"] = weekly_hours
        sub["consecutive_periods"] = consecutive_periods
        sub["credits"] = credits

    return RedirectResponse(url="/subjects", status_code=status.HTTP_302_FOUND)

@router.post("/subjects/delete", response_class=HTMLResponse)
async def delete_subject_entry(
    request: Request,
    subject_id: str = Form(...)
):
    user = get_current_web_user(request)
    if not user or user.get("role") != "timetable_officer":
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

    store.delete_subject(subject_id)
    return RedirectResponse(url="/subjects", status_code=status.HTTP_302_FOUND)

@router.get("/validation", response_class=HTMLResponse)
async def validation_dashboard(request: Request):
    user = get_current_web_user(request)
    if not user or user.get("role") != "timetable_officer":
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

    from app.api.scheduling_routes import get_validation_dashboard
    val_data = await get_validation_dashboard()

    return render_template(request, "validation.html", {
        "request": request,
        "current_user": user,
        "active_page": "validation",
        "validation": val_data
    })

@router.get("/generate", response_class=HTMLResponse)
async def generate_page(request: Request):
    user = get_current_web_user(request)
    if not user or user.get("role") != "timetable_officer":
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

    clusters = []
    for c in store.clusters.values():
        c_copy = c.copy()
        dept = store.get_department(c.get("department_id"))
        c_copy["department_name"] = dept.get("name", "College Department")
        clusters.append(c_copy)

    return render_template(request, "generate.html", {
        "request": request,
        "current_user": user,
        "active_page": "generate",
        "clusters": clusters,
        "solver_result": None
    })

@router.post("/generate", response_class=HTMLResponse)
async def execute_generate(
    request: Request,
    cluster_id: str = Form(...),
    solver_timeout: int = Form(60)
):
    user = get_current_web_user(request)
    if not user or user.get("role") != "timetable_officer":
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

    from app.api.scheduling_routes import _build_cluster_data
    cluster_data = _build_cluster_data(cluster_id)
    cluster_data["solver_timeout_seconds"] = solver_timeout

    orchestrator = TimetableAgentOrchestrator()
    result = orchestrator.generate_and_optimize(cluster_data)

    gen_id = str(uuid.uuid4())
    if result["success"]:
        store.timetable_generations[gen_id] = {
            "id": gen_id,
            "cluster_id": cluster_id,
            "generated_by": user["id"],
            "solver_status": result["solver_status"],
            "status": "draft",
            "solve_time_seconds": result["solve_time_seconds"],
            "input_snapshot": copy.deepcopy(cluster_data),
            "created_at": datetime.utcnow().isoformat()
        }
        for e in result.get("entries", []):
            e_id = str(uuid.uuid4())
            e_copy = e.copy()
            e_copy["id"] = e_id
            e_copy["generation_id"] = gen_id
            store.timetable_entries[e_id] = e_copy

    solver_res = {
        "generation_id": gen_id,
        "solver_status": result.get("solver_status"),
        "solve_time_seconds": result.get("solve_time_seconds", 0.0),
        "entries_count": len(result.get("entries", []))
    }

    clusters = []
    for c in store.clusters.values():
        c_copy = c.copy()
        dept = store.get_department(c.get("department_id"))
        c_copy["department_name"] = dept.get("name", "College Department")
        clusters.append(c_copy)

    return render_template(request, "generate.html", {
        "request": request,
        "current_user": user,
        "active_page": "generate",
        "clusters": clusters,
        "solver_result": solver_res
    })

@router.get("/viewer", response_class=HTMLResponse)
async def viewer_page(
    request: Request,
    gen: Optional[str] = None,
    section_id: Optional[str] = None,
    faculty_id: Optional[str] = None
):
    user = get_current_web_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    active_gen_id = gen or next(
        (g["id"] for g in store.timetable_generations.values() if g.get("status") == "published"),
        next((g["id"] for g in store.timetable_generations.values()), None)
    )

    entries = []
    if active_gen_id:
        all_e = [e for e in store.timetable_entries.values() if e.get("generation_id") == active_gen_id]
        if section_id:
            all_e = [e for e in all_e if e.get("section_id") == section_id]
        if faculty_id:
            all_e = [e for e in all_e if e.get("faculty_id") == faculty_id or faculty_id in e.get("co_faculty_ids", [])]

        for e in all_e:
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

            entries.append({
                "day_of_week": e.get("day_of_week", slot.get("day_of_week")),
                "period_number": e.get("period_number", slot.get("period_number")),
                "start_time": e.get("start_time", slot.get("start_time")),
                "end_time": e.get("end_time", slot.get("end_time")),
                "section_name": sec.get("name", ""),
                "subject_code": sub.get("subject_code", ""),
                "subject_name": sub.get("subject_name", ""),
                "faculty_name": fac.get("full_name", ""),
                "co_faculty_names": co_fac_names,
                "room_code": room.get("room_code", ""),
                "lab_name": lab.get("lab_name", ""),
                "batch_name": batch.get("batch_name", ""),
                "entry_type": e.get("entry_type", "regular")
            })

    entries.sort(key=lambda x: (x.get("day_of_week", 0), x.get("period_number", 0)))
    day_names = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday"}

    return render_template(request, "viewer.html", {
        "request": request,
        "current_user": user,
        "active_page": "viewer",
        "active_gen_id": active_gen_id,
        "entries": entries,
        "sections": list(store.sections.values()),
        "faculty": list(store.faculty.values()),
        "classrooms": list(store.classrooms.values()),
        "laboratories": list(store.laboratories.values()),
        "selected_section": section_id,
        "selected_faculty": faculty_id,
        "day_names": day_names
    })

@router.get("/editor", response_class=HTMLResponse)
async def editor_page(request: Request):
    user = get_current_web_user(request)
    if not user or user.get("role") != "timetable_officer":
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

    active_gen_id = next((g["id"] for g in store.timetable_generations.values()), None)
    entries = []
    if active_gen_id:
        for e in store.timetable_entries.values():
            if e.get("generation_id") == active_gen_id:
                sec = store.sections.get(e.get("section_id"), {})
                sub = store.subjects.get(e.get("subject_id"), {})
                fac = store.faculty.get(e.get("faculty_id"), {})
                entries.append({
                    "id": e["id"],
                    "day_of_week": e.get("day_of_week", 1),
                    "period_number": e.get("period_number", 1),
                    "subject_code": sub.get("subject_code", ""),
                    "section_name": sec.get("name", ""),
                    "faculty_name": fac.get("full_name", "")
                })

    day_names = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri"}
    slots = list(store.time_slots.values())
    slots.sort(key=lambda s: (s["day_of_week"], s["period_number"]))

    return render_template(request, "editor.html", {
        "request": request,
        "current_user": user,
        "active_page": "editor",
        "entries": entries,
        "time_slots": slots,
        "faculty": list(store.faculty.values()),
        "classrooms": list(store.classrooms.values()),
        "laboratories": list(store.laboratories.values()),
        "day_names": day_names,
        "edit_result": None
    })

@router.post("/editor/modify", response_class=HTMLResponse)
async def modify_entry(
    request: Request,
    entry_id: str = Form(...),
    new_time_slot_id: Optional[str] = Form(None),
    new_faculty_id: Optional[str] = Form(None),
    new_classroom_id: Optional[str] = Form(None),
    new_laboratory_id: Optional[str] = Form(None)
):
    user = get_current_web_user(request)
    if not user or user.get("role") != "timetable_officer":
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

    entry = store.timetable_entries.get(entry_id)
    if entry:
        if new_time_slot_id:
            slot = store.time_slots.get(new_time_slot_id)
            if slot:
                entry["time_slot_id"] = new_time_slot_id
                entry["day_of_week"] = slot["day_of_week"]
                entry["period_number"] = slot["period_number"]
                entry["start_time"] = slot["start_time"]
                entry["end_time"] = slot["end_time"]
        if new_faculty_id:
            entry["faculty_id"] = new_faculty_id
        if new_classroom_id:
            entry["classroom_id"] = new_classroom_id
        if new_laboratory_id:
            entry["laboratory_id"] = new_laboratory_id

    # Re-validate with Conflict Checker
    gen_id = entry.get("generation_id") if entry else None
    all_e = [e for e in store.timetable_entries.values() if e.get("generation_id") == gen_id]
    validator = TimetableConflictValidator(
        entries=all_e,
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

    slots = list(store.time_slots.values())
    slots.sort(key=lambda s: (s["day_of_week"], s["period_number"]))
    day_names = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri"}

    entries = []
    if gen_id:
        for e in store.timetable_entries.values():
            if e.get("generation_id") == gen_id:
                sec = store.sections.get(e.get("section_id"), {})
                sub = store.subjects.get(e.get("subject_id"), {})
                fac = store.faculty.get(e.get("faculty_id"), {})
                entries.append({
                    "id": e["id"],
                    "day_of_week": e.get("day_of_week", 1),
                    "period_number": e.get("period_number", 1),
                    "subject_code": sub.get("subject_code", ""),
                    "section_name": sec.get("name", ""),
                    "faculty_name": fac.get("full_name", "")
                })

    return render_template(request, "editor.html", {
        "request": request,
        "current_user": user,
        "active_page": "editor",
        "entries": entries,
        "time_slots": slots,
        "faculty": list(store.faculty.values()),
        "classrooms": list(store.classrooms.values()),
        "laboratories": list(store.laboratories.values()),
        "day_names": day_names,
        "edit_result": {
            "has_conflicts": len(conflicts) > 0,
            "conflicts_count": len(conflicts),
            "conflicts": conflicts
        }
    })

@router.get("/academic", response_class=HTMLResponse)
async def academic_page(request: Request):
    user = get_current_web_user(request)
    if not user or user.get("role") != "timetable_officer":
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

    # Enrich clusters and sections with dynamic department info
    clusters = []
    for c in store.clusters.values():
        c_copy = c.copy()
        dept = store.get_department(c.get("department_id"))
        c_copy["department_name"] = dept.get("name", "College Department")
        c_copy["department_code"] = dept.get("code", "")
        clusters.append(c_copy)

    sections = []
    for s in store.sections.values():
        s_copy = s.copy()
        dept = store.get_department(s.get("department_id"))
        s_copy["department_name"] = dept.get("name", "College Department")
        s_copy["department_code"] = dept.get("code", "")
        sections.append(s_copy)

    return render_template(request, "academic.html", {
        "request": request,
        "current_user": user,
        "active_page": "academic",
        "clusters": clusters,
        "sections": sections,
        "departments": list(store.departments.values())
    })

@router.post("/academic/department/create", response_class=HTMLResponse)
async def create_department(
    request: Request,
    name: str = Form(...),
    code: str = Form(...)
):
    user = get_current_web_user(request)
    if not user or user.get("role") != "timetable_officer":
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

    autoincrement_id = store.get_next_dept_id()
    str_id = str(autoincrement_id)
    store.departments[str_id] = {
        "id": autoincrement_id,
        "name": name.strip(),
        "code": code.strip().upper(),
        "created_at": datetime.utcnow().isoformat()
    }
    return RedirectResponse(url="/academic", status_code=status.HTTP_302_FOUND)

@router.post("/academic/department/edit", response_class=HTMLResponse)
async def edit_department(
    request: Request,
    department_id: str = Form(...),
    name: str = Form(...),
    code: str = Form(...)
):
    user = get_current_web_user(request)
    if not user or user.get("role") != "timetable_officer":
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

    dept = store.get_department(department_id)
    if dept:
        dept["name"] = name.strip()
        dept["code"] = code.strip().upper()

    return RedirectResponse(url="/academic", status_code=status.HTTP_302_FOUND)

@router.post("/academic/department/delete", response_class=HTMLResponse)
async def delete_department(
    request: Request,
    department_id: str = Form(...)
):
    user = get_current_web_user(request)
    if not user or user.get("role") != "timetable_officer":
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

    store.delete_department(department_id)
    return RedirectResponse(url="/academic", status_code=status.HTTP_302_FOUND)

@router.post("/academic/section/create", response_class=HTMLResponse)
async def create_section_entry(
    request: Request,
    name: str = Form(...),
    department_id: str = Form(...),
    student_strength: int = Form(60)
):
    user = get_current_web_user(request)
    if not user or user.get("role") != "timetable_officer":
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

    s_id = str(uuid.uuid4())
    sem_id = next(iter(store.semesters.keys()), "s5555555-5555-5555-5555-555555555555")
    cluster_id = next(iter(store.clusters.keys()), "c1111111-1111-1111-1111-111111111111")

    store.sections[s_id] = {
        "id": s_id,
        "name": name.strip().upper(),
        "department_id": department_id,
        "semester_id": sem_id,
        "student_strength": student_strength,
        "cluster_id": cluster_id
    }
    store.cluster_sections.append({"cluster_id": cluster_id, "section_id": s_id})

    # Create 2 lab batches
    half = student_strength // 2
    b1_id = str(uuid.uuid4())
    b2_id = str(uuid.uuid4())
    store.lab_batches[b1_id] = {
        "id": b1_id,
        "section_id": s_id,
        "batch_name": f"Batch {name.strip().upper()}1",
        "student_count": half
    }
    store.lab_batches[b2_id] = {
        "id": b2_id,
        "section_id": s_id,
        "batch_name": f"Batch {name.strip().upper()}2",
        "student_count": student_strength - half
    }

    for slot_id in store.time_slots.keys():
        store.section_availability[f"{s_id}_{slot_id}"] = True

    return RedirectResponse(url="/academic", status_code=status.HTTP_302_FOUND)

@router.post("/academic/section/edit", response_class=HTMLResponse)
async def edit_section_entry(
    request: Request,
    section_id: str = Form(...),
    name: str = Form(...),
    department_id: str = Form(...),
    student_strength: int = Form(60)
):
    user = get_current_web_user(request)
    if not user or user.get("role") != "timetable_officer":
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

    sec = store.sections.get(section_id)
    if sec:
        sec["name"] = name.strip().upper()
        sec["department_id"] = department_id
        sec["student_strength"] = student_strength

    return RedirectResponse(url="/academic", status_code=status.HTTP_302_FOUND)

@router.post("/academic/section/delete", response_class=HTMLResponse)
async def delete_section_entry(
    request: Request,
    section_id: str = Form(...)
):
    user = get_current_web_user(request)
    if not user or user.get("role") != "timetable_officer":
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

    store.delete_section(section_id)
    return RedirectResponse(url="/academic", status_code=status.HTTP_302_FOUND)

@router.get("/rooms-labs", response_class=HTMLResponse)
async def rooms_labs_page(request: Request):
    user = get_current_web_user(request)
    if not user or user.get("role") != "timetable_officer":
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

    staffing = []
    for st in store.lab_staffing_requirements.values():
        sec = store.sections.get(st.get("section_id"), {})
        sub = store.subjects.get(st.get("subject_id"), {})
        lab = store.laboratories.get(st.get("lab_id"), {})
        fac = store.faculty.get(st.get("primary_faculty_id"), {})
        staffing.append({
            "section_name": sec.get("name", ""),
            "subject_name": sub.get("subject_name", ""),
            "lab_name": lab.get("lab_code", ""),
            "primary_faculty_name": fac.get("full_name", "Unassigned"),
            "required_co_teacher_count": st.get("required_co_teacher_count", 0),
            "consecutive_periods": st.get("consecutive_periods", 2)
        })

    batches = []
    for b in store.lab_batches.values():
        sec = store.sections.get(b.get("section_id"), {})
        batches.append({
            "section_name": sec.get("name", ""),
            "batch_name": b.get("batch_name", ""),
            "student_count": b.get("student_count", 0)
        })

    return render_template(request, "rooms_labs.html", {
        "request": request,
        "current_user": user,
        "active_page": "rooms-labs",
        "classrooms": list(store.classrooms.values()),
        "laboratories": list(store.laboratories.values()),
        "lab_staffing": staffing,
        "lab_batches": batches
    })

@router.post("/rooms/create", response_class=HTMLResponse)
async def create_room(
    request: Request,
    room_code: str = Form(...),
    room_name: str = Form(...),
    capacity: int = Form(75),
    room_type: str = Form("classroom")
):
    user = get_current_web_user(request)
    if not user or user.get("role") != "timetable_officer":
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

    r_id = str(uuid.uuid4())
    store.classrooms[r_id] = {
        "id": r_id,
        "room_code": room_code.strip().upper(),
        "room_name": room_name.strip(),
        "capacity": capacity,
        "room_type": room_type.strip(),
        "is_active": True
    }
    for s_id in store.time_slots.keys():
        store.classroom_availability[f"{r_id}_{s_id}"] = True

    return RedirectResponse(url="/rooms-labs", status_code=status.HTTP_302_FOUND)

@router.post("/rooms/edit", response_class=HTMLResponse)
async def edit_room(
    request: Request,
    room_id: str = Form(...),
    room_code: str = Form(...),
    room_name: str = Form(...),
    capacity: int = Form(75),
    room_type: str = Form("classroom")
):
    user = get_current_web_user(request)
    if not user or user.get("role") != "timetable_officer":
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

    cr = store.classrooms.get(room_id)
    if cr:
        cr["room_code"] = room_code.strip().upper()
        cr["room_name"] = room_name.strip()
        cr["capacity"] = capacity
        cr["room_type"] = room_type.strip()

    return RedirectResponse(url="/rooms-labs", status_code=status.HTTP_302_FOUND)

@router.post("/rooms/delete", response_class=HTMLResponse)
async def delete_room(
    request: Request,
    room_id: str = Form(...)
):
    user = get_current_web_user(request)
    if not user or user.get("role") != "timetable_officer":
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

    store.delete_classroom(room_id)
    return RedirectResponse(url="/rooms-labs", status_code=status.HTTP_302_FOUND)

@router.post("/labs/create", response_class=HTMLResponse)
async def create_lab(
    request: Request,
    lab_code: str = Form(...),
    lab_name: str = Form(...),
    lab_type: str = Form("software"),
    student_capacity: int = Form(35),
    workstation_capacity: int = Form(35),
    equipment_details: Optional[str] = Form(None)
):
    user = get_current_web_user(request)
    if not user or user.get("role") != "timetable_officer":
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

    l_id = str(uuid.uuid4())
    store.laboratories[l_id] = {
        "id": l_id,
        "lab_code": lab_code.strip().upper(),
        "lab_name": lab_name.strip(),
        "lab_type": lab_type.strip(),
        "student_capacity": student_capacity,
        "workstation_capacity": workstation_capacity,
        "equipment_details": equipment_details.strip() if equipment_details else "Standard laboratory hardware",
        "is_active": True
    }
    for s_id in store.time_slots.keys():
        store.lab_availability[f"{l_id}_{s_id}"] = True

    return RedirectResponse(url="/rooms-labs", status_code=status.HTTP_302_FOUND)

@router.post("/labs/edit", response_class=HTMLResponse)
async def edit_lab(
    request: Request,
    lab_id: str = Form(...),
    lab_code: str = Form(...),
    lab_name: str = Form(...),
    lab_type: str = Form("software"),
    student_capacity: int = Form(35),
    workstation_capacity: int = Form(35),
    equipment_details: Optional[str] = Form(None)
):
    user = get_current_web_user(request)
    if not user or user.get("role") != "timetable_officer":
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

    lab = store.laboratories.get(lab_id)
    if lab:
        lab["lab_code"] = lab_code.strip().upper()
        lab["lab_name"] = lab_name.strip()
        lab["lab_type"] = lab_type.strip()
        lab["student_capacity"] = student_capacity
        lab["workstation_capacity"] = workstation_capacity
        if equipment_details:
            lab["equipment_details"] = equipment_details.strip()

    return RedirectResponse(url="/rooms-labs", status_code=status.HTTP_302_FOUND)

@router.post("/labs/delete", response_class=HTMLResponse)
async def delete_lab(
    request: Request,
    lab_id: str = Form(...)
):
    user = get_current_web_user(request)
    if not user or user.get("role") != "timetable_officer":
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

    store.delete_laboratory(lab_id)
    return RedirectResponse(url="/rooms-labs", status_code=status.HTTP_302_FOUND)

@router.get("/availability", response_class=HTMLResponse)
async def availability_page(request: Request):
    user = get_current_web_user(request)
    if not user or user.get("role") != "timetable_officer":
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

    day_names = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri"}
    return render_template(request, "availability.html", {
        "request": request,
        "current_user": user,
        "active_page": "availability",
        "faculty": list(store.faculty.values()),
        "sections": list(store.sections.values()),
        "classrooms": list(store.classrooms.values()),
        "laboratories": list(store.laboratories.values()),
        "day_names": day_names
    })

@router.get("/electives", response_class=HTMLResponse)
async def electives_page(request: Request):
    user = get_current_web_user(request)
    if not user or user.get("role") != "timetable_officer":
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

    res = []
    for grp in store.elective_groups.values():
        g_copy = grp.copy()
        opts = [o for o in store.elective_options.values() if o.get("elective_group_id") == grp["id"]]
        g_copy["options"] = opts
        res.append(g_copy)

    return render_template(request, "electives.html", {
        "request": request,
        "current_user": user,
        "active_page": "electives",
        "electives": res
    })

@router.get("/ai-advisory", response_class=HTMLResponse)
async def ai_advisory_page(request: Request):
    user = get_current_web_user(request)
    if not user or user.get("role") != "timetable_officer":
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

    return render_template(request, "ai_advisory.html", {
        "request": request,
        "current_user": user,
        "active_page": "ai-advisory",
        "advisory_text": None
    })

@router.post("/ai-advisory/run", response_class=HTMLResponse)
async def run_ai_advisory(request: Request):
    user = get_current_web_user(request)
    if not user or user.get("role") != "timetable_officer":
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

    from app.api.scheduling_routes import _build_cluster_data
    cluster_id = next(iter(store.clusters.keys()), "")
    cluster_data = _build_cluster_data(cluster_id) if cluster_id else {}

    orchestrator = TimetableAgentOrchestrator()
    pre_analysis = orchestrator.run_pre_generation_analysis(cluster_data)
    advisory_text = await orchestrator.generate_gemini_advisory({
        "cluster_name": cluster_data.get("cluster", {}).get("name", "Cluster 1"),
        "sections_count": len(cluster_data.get("sections", [])),
        "faculty_count": len(cluster_data.get("faculty", [])),
        "classrooms_count": len(cluster_data.get("classrooms", [])),
        "laboratories_count": len(cluster_data.get("laboratories", [])),
        "findings": pre_analysis.get("findings", [])
    })

    return render_template(request, "ai_advisory.html", {
        "request": request,
        "current_user": user,
        "active_page": "ai-advisory",
        "advisory_text": advisory_text
    })

@router.get("/excel-tools", response_class=HTMLResponse)
async def excel_tools_page(request: Request):
    user = get_current_web_user(request)
    if not user or user.get("role") != "timetable_officer":
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

    active_gen_id = next((g["id"] for g in store.timetable_generations.values()), None)
    return render_template(request, "excel_tools.html", {
        "request": request,
        "current_user": user,
        "active_page": "excel-tools",
        "active_gen_id": active_gen_id
    })

@router.get("/my-schedule", response_class=HTMLResponse)
async def my_schedule_page(request: Request):
    user = get_current_web_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

@router.get("/my-labs", response_class=HTMLResponse)
async def my_labs_page(request: Request):
    user = get_current_web_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

@router.get("/excel/export/timetable/{generation_id}")
async def export_timetable_alias(generation_id: str, format: str = "xlsx"):
    from app.api.excel_routes import export_timetable
    return await export_timetable(generation_id=generation_id, format=format)

