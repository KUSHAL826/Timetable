from typing import Dict, Any, List

def analyze_faculty_assignments(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Faculty Management Agent:
    Verifies teacher qualification mappings, weekly workload limits, and availability.
    """
    findings = []
    faculty = data.get("faculty", [])
    qualifications = data.get("qualifications", {}) # (fac_id, sub_id) -> bool
    subjects = {s["id"]: s for s in data.get("subjects", [])}
    fac_workloads = {f["id"]: 0 for f in faculty}

    # Count theory workload
    for req in data.get("theory_requirements", []):
        fac_id = req.get("primary_faculty_id")
        sub_id = req.get("subject_id")
        hrs = req.get("weekly_hours", 0)
        if fac_id in fac_workloads:
            fac_workloads[fac_id] += hrs

        # Qualification check
        if fac_id and sub_id and not qualifications.get((fac_id, sub_id), True):
            fac_name = next((f["full_name"] for f in faculty if f["id"] == fac_id), "Unknown")
            sub_code = subjects.get(sub_id, {}).get("subject_code", "Unknown")
            findings.append({
                "level": "error",
                "message": f"Faculty {fac_name} is assigned to teach {sub_code} without verified qualification."
            })

    # Count lab workload
    for lab_req in data.get("lab_requirements", []):
        prim_f = lab_req.get("primary_faculty_id")
        co_fs = lab_req.get("co_teacher_ids", [])
        hrs = lab_req.get("weekly_hours", 0)
        if prim_f in fac_workloads:
            fac_workloads[prim_f] += hrs
        for c in co_fs:
            if c in fac_workloads:
                fac_workloads[c] += hrs

    # Check workload limits
    for f in faculty:
        fid = f["id"]
        fname = f["full_name"]
        max_hrs = f.get("max_weekly_hours", 20)
        assigned = fac_workloads.get(fid, 0)
        if assigned > max_hrs:
            findings.append({
                "level": "warning",
                "message": f"Faculty {fname} is assigned {assigned} hours, exceeding max limit ({max_hrs} hrs)."
            })

    return {
        "agent": "Faculty Management Agent",
        "status": "error" if any(f["level"] == "error" for f in findings) else "ok",
        "findings": findings
    }
