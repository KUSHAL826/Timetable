from typing import Dict, List, Any

class ConflictDiagnostics:
    """
    Analyzes why a timetable schedule model is INFEASIBLE or constrained,
    and provides actionable guidance for the Timetable Officer.
    """

    @staticmethod
    def diagnose_infeasibility(data: Dict[str, Any]) -> Dict[str, Any]:
        bottlenecks = []
        suggestions = []

        total_schedulable_slots = len([s for s in data.get("time_slots", []) if s.get("is_schedulable", True)])
        sections = data.get("sections", [])
        subjects = {s["id"]: s for s in data.get("subjects", [])}
        classrooms = data.get("classrooms", [])
        laboratories = data.get("laboratories", [])

        # 1. Check Section Capacity vs Period Capacity
        for sec in sections:
            sec_id = sec["id"]
            sec_name = sec["name"]
            theory_reqs = [r for r in data.get("theory_requirements", []) if r["section_id"] == sec_id]
            lab_reqs = [r for r in data.get("lab_requirements", []) if r["section_id"] == sec_id]

            total_hours = sum(r["weekly_hours"] for r in theory_reqs) + sum(r["weekly_hours"] for r in lab_reqs)
            if total_hours > total_schedulable_slots:
                bottlenecks.append({
                    "entity": f"Section {sec_name}",
                    "issue": f"Required hours ({total_hours}) exceed total schedulable weekly periods ({total_schedulable_slots}).",
                    "severity": "CRITICAL"
                })
                suggestions.append(f"Reduce weekly subject hours for Section {sec_name} or add more time periods in the academic week.")

        # 2. Check Classroom Sizing Bottlenecks
        max_class_strength = max((s["student_strength"] for s in sections), default=0)
        max_room_capacity = max((r["capacity"] for r in classrooms), default=0)
        if max_class_strength > max_room_capacity:
            bottlenecks.append({
                "entity": "Classrooms",
                "issue": f"Largest section has {max_class_strength} students, but largest classroom has capacity {max_room_capacity}.",
                "severity": "CRITICAL"
            })
            suggestions.append("Add a larger lecture hall or split the large section.")

        # 3. Check Lab Staffing & Availability Bottlenecks
        for lab_req in data.get("lab_requirements", []):
            sec_name = next((s["name"] for s in sections if s["id"] == lab_req["section_id"]), "Unknown")
            sub_code = subjects.get(lab_req["subject_id"], {}).get("subject_code", "Unknown")
            required_co = lab_req.get("required_co_teacher_count", 0)
            assigned_co = len(lab_req.get("co_teacher_ids", []))

            if assigned_co < required_co:
                bottlenecks.append({
                    "entity": f"Lab {sub_code} for Section {sec_name}",
                    "issue": f"Requires {required_co} co-teachers, but only {assigned_co} are assigned.",
                    "severity": "CRITICAL"
                })
                suggestions.append(f"Assign {required_co - assigned_co} more qualified co-teachers for {sub_code} ({sec_name}).")

        # 4. Check Lab Capacity vs Batch Sizes
        labs_map = {l["id"]: l for l in laboratories}
        for lab_req in data.get("lab_requirements", []):
            lab = labs_map.get(lab_req["lab_id"])
            if lab:
                for b in lab_req.get("batches", []):
                    if b["student_count"] > lab["student_capacity"]:
                        bottlenecks.append({
                            "entity": f"Lab {lab['lab_code']} vs {b['batch_name']}",
                            "issue": f"Batch strength {b['student_count']} exceeds lab student capacity {lab['student_capacity']}.",
                            "severity": "CRITICAL"
                        })
                        suggestions.append(f"Reduce batch size for {b['batch_name']} or reassign to a laboratory with higher capacity.")

        return {
            "status": "DIAGNOSIS_COMPLETE",
            "bottlenecks_found": len(bottlenecks),
            "bottlenecks": bottlenecks,
            "suggestions": suggestions,
        }
