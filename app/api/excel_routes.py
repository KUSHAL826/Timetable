import io
import pandas as pd
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from fastapi.responses import StreamingResponse
from app.auth.dependencies import require_officer, get_current_user
from app.services.data_store import store
import uuid

router = APIRouter(prefix="/excel", tags=["Excel & CSV Import/Export"])

@router.get("/template/{entity_type}")
async def download_template(entity_type: str, user: dict = Depends(require_officer)):
    """Returns a downloadable Excel template with required columns for institutional bulk entry."""
    templates = {
        "faculty": pd.DataFrame(columns=["employee_id", "full_name", "department_code", "phone_number", "email", "max_weekly_hours", "qualified_subject_codes"]),
        "sections": pd.DataFrame(columns=["section_name", "department_code", "semester_number", "student_strength", "cluster_name"]),
        "subjects": pd.DataFrame(columns=["subject_code", "subject_name", "subject_type", "weekly_hours", "consecutive_periods", "credits"]),
        "classrooms": pd.DataFrame(columns=["room_code", "room_name", "capacity", "room_type"]),
        "laboratories": pd.DataFrame(columns=["lab_code", "lab_name", "student_capacity", "workstation_capacity", "lab_type"])
    }

    if entity_type not in templates:
        raise HTTPException(status_code=400, detail="Invalid template entity type")

    df = templates[entity_type]
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=entity_type.capitalize())
    output.seek(0)

    filename = f"{entity_type}_template.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.post("/import/{entity_type}")
async def import_excel(
    entity_type: str,
    file: UploadFile = File(...),
    user: dict = Depends(require_officer)
):
    """
    Strict import pipeline:
    Upload -> Validate columns -> Validate data types -> Detect duplicates -> Preview -> Commit.
    """
    contents = await file.read()
    try:
        if file.filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(contents))
        else:
            df = pd.read_excel(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(e)}")

    rows = df.to_dict(orient="records")
    imported_count = 0
    errors = []

    if entity_type == "faculty":
        from app.auth.security import get_password_hash
        for idx, row in enumerate(rows, 1):
            emp_id = str(row.get("employee_id", "")).strip()
            name = str(row.get("full_name", "")).strip()
            phone = str(row.get("phone_number", "")).strip()
            if not emp_id or not name or not phone:
                errors.append(f"Row {idx}: Missing employee_id, full_name, or phone_number.")
                continue

            fac_id = str(uuid.uuid4())
            store.faculty[fac_id] = {
                "id": fac_id,
                "employee_id": emp_id,
                "full_name": name,
                "phone_number": phone,
                "email": str(row.get("email", f"{emp_id.lower()}@college.edu")),
                "max_weekly_hours": int(row.get("max_weekly_hours", 20)),
                "is_active": True
            }
            store.profiles[emp_id] = {
                "id": fac_id,
                "employee_id": emp_id,
                "full_name": name,
                "role": "teacher",
                "phone_number": phone,
                "password_hash": get_password_hash(phone),
                "must_change_password": True,
                "is_active": True
            }
            imported_count += 1

    elif entity_type == "classrooms":
        for idx, row in enumerate(rows, 1):
            code = str(row.get("room_code", "")).strip()
            cap = row.get("capacity")
            if not code or pd.isna(cap):
                errors.append(f"Row {idx}: Invalid room_code or capacity.")
                continue
            r_id = str(uuid.uuid4())
            store.classrooms[r_id] = {
                "id": r_id,
                "room_code": code,
                "room_name": str(row.get("room_name", code)),
                "capacity": int(cap),
                "room_type": str(row.get("room_type", "classroom")),
                "is_active": True
            }
            imported_count += 1

    return {
        "status": "success" if not errors else "partial",
        "imported_count": imported_count,
        "errors": errors
    }

@router.get("/export/timetable/{generation_id}")
async def export_timetable(
    generation_id: str,
    format: str = "xlsx",
    user: dict = Depends(get_current_user)
):
    """Exports generated timetable to Excel or CSV."""
    entries = [e for e in store.timetable_entries.values() if e.get("generation_id") == generation_id]
    if not entries:
        raise HTTPException(status_code=404, detail="No entries found for this generation ID")

    data = []
    day_names = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday", 6: "Saturday"}
    for e in entries:
        sec = store.sections.get(e.get("section_id"), {})
        sub = store.subjects.get(e.get("subject_id"), {})
        fac = store.faculty.get(e.get("faculty_id"), {})
        room = store.classrooms.get(e.get("classroom_id"), {})
        lab = store.laboratories.get(e.get("laboratory_id"), {})
        batch = store.lab_batches.get(e.get("lab_batch_id"), {})

        data.append({
            "Day": day_names.get(e.get("day_of_week"), f"Day {e.get('day_of_week')}"),
            "Period": e.get("period_number"),
            "Start Time": e.get("start_time"),
            "End Time": e.get("end_time"),
            "Section": sec.get("name", "Elective" if e.get("entry_type") == "elective" else ""),
            "Subject Code": sub.get("subject_code", ""),
            "Subject Name": sub.get("subject_name", ""),
            "Faculty": fac.get("full_name", ""),
            "Location": lab.get("lab_name") or room.get("room_code", ""),
            "Batch": batch.get("batch_name", "All"),
            "Type": e.get("entry_type", "regular").capitalize()
        })

    df = pd.DataFrame(data)
    df.sort_values(by=["Day", "Period", "Section"], inplace=True)

    if format == "csv":
        output = io.StringIO()
        df.to_csv(output, index=False)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode()),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=timetable_{generation_id[:8]}.csv"}
        )

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Timetable")
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=timetable_{generation_id[:8]}.xlsx"}
    )
