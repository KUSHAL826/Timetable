from typing import Dict, Any, List

def analyze_electives_structure(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Professional Elective Agent:
    Validates elective groupings, student aggregate counts, and classroom capacities.
    """
    findings = []
    classrooms = {c["id"]: c for c in data.get("classrooms", [])}

    for grp in data.get("elective_groups", []):
        grp_name = grp.get("group_name", "Elective Group")
        options = grp.get("options", [])
        if not options:
            findings.append({
                "level": "error",
                "message": f"Elective group '{grp_name}' contains no elective course options."
            })
            continue

        for opt in options:
            sub_name = opt.get("subject_name", "Elective Subject")
            fac_id = opt.get("faculty_id")
            room_id = opt.get("classroom_id")
            total_students = opt.get("total_students", 0)

            if not fac_id:
                findings.append({
                    "level": "error",
                    "message": f"Elective option '{sub_name}' in '{grp_name}' has no assigned faculty."
                })

            if not room_id:
                findings.append({
                    "level": "error",
                    "message": f"Elective option '{sub_name}' in '{grp_name}' has no designated classroom."
                })
            else:
                room = classrooms.get(room_id, {})
                if room.get("capacity", 0) < total_students:
                    findings.append({
                        "level": "error",
                        "message": f"Classroom {room.get('room_code')} capacity ({room.get('capacity')}) is too small for elective '{sub_name}' ({total_students} students)."
                    })

    return {
        "agent": "Professional Elective Agent",
        "status": "error" if any(f["level"] == "error" for f in findings) else "ok",
        "findings": findings
    }
