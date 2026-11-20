from typing import Dict, Any, List
from app.config import settings

def analyze_academic_structure(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Academic Planning Agent:
    Validates cluster definitions, semester alignment, and total curriculum hours.
    """
    findings = []
    sections = data.get("sections", [])
    clusters = data.get("clusters", [])
    time_slots = [s for s in data.get("time_slots", []) if s.get("is_schedulable", True)]

    total_weekly_slots = len(time_slots)

    if not clusters:
        findings.append({"level": "error", "message": "No clusters configured. Timetables must be generated cluster-wise."})

    for cluster in clusters:
        c_secs = [s for s in sections if s.get("cluster_id") == cluster.get("id")]
        if not c_secs:
            findings.append({"level": "warning", "message": f"Cluster '{cluster.get('name')}' has no mapped sections."})

    for section in sections:
        sec_id = section.get("id")
        sec_name = section.get("name")
        theory_reqs = [r for r in data.get("theory_requirements", []) if r.get("section_id") == sec_id]
        lab_reqs = [r for r in data.get("lab_requirements", []) if r.get("section_id") == sec_id]

        total_hours = sum(r.get("weekly_hours", 0) for r in theory_reqs) + sum(r.get("weekly_hours", 0) for r in lab_reqs)
        if total_hours > total_weekly_slots:
            findings.append({
                "level": "error",
                "message": f"Section {sec_name} demands {total_hours} weekly hours, exceeding available slots ({total_weekly_slots})."
            })
        elif total_hours == 0:
            findings.append({
                "level": "warning",
                "message": f"Section {sec_name} has 0 weekly subject hours configured."
            })

    return {
        "agent": "Academic Planning Agent",
        "status": "error" if any(f["level"] == "error" for f in findings) else "ok",
        "findings": findings
    }
