from typing import Dict, Any, List

def analyze_laboratory_staffing(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Laboratory Management Agent:
    Validates lab capacities, primary faculty, required co-teacher count, and batches.
    """
    findings = []
    laboratories = {l["id"]: l for l in data.get("laboratories", [])}
    subjects = {s["id"]: s for s in data.get("subjects", [])}
    sections = {s["id"]: s for s in data.get("sections", [])}

    for lab_req in data.get("lab_requirements", []):
        lab_id = lab_req.get("lab_id")
        sub_id = lab_req.get("subject_id")
        sec_id = lab_req.get("section_id")
        req_co = lab_req.get("required_co_teacher_count", 0)
        assigned_co = len(lab_req.get("co_teacher_ids", []))
        prim_fac = lab_req.get("primary_faculty_id")

        lab = laboratories.get(lab_id, {})
        sub = subjects.get(sub_id, {})
        sec = sections.get(sec_id, {})

        if not prim_fac:
            findings.append({
                "level": "error",
                "message": f"Practical subject {sub.get('subject_code')} in section {sec.get('name')} has no primary faculty assigned."
            })

        if assigned_co != req_co:
            findings.append({
                "level": "error",
                "message": f"Practical subject {sub.get('subject_code')} requires {req_co} co-teachers, but {assigned_co} are assigned."
            })

        # Batches & capacities
        batches = lab_req.get("batches", [])
        if not batches:
            findings.append({
                "level": "error",
                "message": f"No student batches defined for practical subject {sub.get('subject_code')} in section {sec.get('name')}."
            })
        else:
            for b in batches:
                if b.get("student_count", 0) > lab.get("student_capacity", 0):
                    findings.append({
                        "level": "error",
                        "message": f"Batch '{b.get('batch_name')}' size ({b.get('student_count')}) exceeds lab {lab.get('lab_code')} capacity ({lab.get('student_capacity')})."
                    })

    return {
        "agent": "Laboratory Management Agent",
        "status": "error" if any(f["level"] == "error" for f in findings) else "ok",
        "findings": findings
    }
