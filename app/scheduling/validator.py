from typing import List, Dict, Any, Optional
from collections import defaultdict
import uuid

class TimetableConflictValidator:
    """
    Independent Conflict and Feasibility Validator.
    Checks any proposed timetable schedule (automatic or manually edited)
    against institutional hard rules and resource limits.
    """

    def __init__(
        self,
        entries: List[Dict[str, Any]],
        sections: Dict[str, Any],
        subjects: Dict[str, Any],
        faculty: Dict[str, Any],
        classrooms: Dict[str, Any],
        laboratories: Dict[str, Any],
        batches: Dict[str, Any],
        qualifications: Dict[str, Any],
        availability: Dict[str, Any]
    ):
        self.entries = entries
        self.sections = sections
        self.subjects = subjects
        self.faculty = faculty
        self.classrooms = classrooms
        self.labs = laboratories
        self.batches = batches
        self.qualifications = qualifications # (fac_id, sub_id) -> bool
        self.availability = availability

    def validate_all(self) -> List[Dict[str, Any]]:
        conflicts = []

        # 1. Check Faculty Clashes
        # Map (faculty_id, time_slot_id) -> list of entry references
        fac_slot_map = defaultdict(list)
        # 2. Check Classroom Clashes
        room_slot_map = defaultdict(list)
        # 3. Check Lab Clashes
        lab_slot_map = defaultdict(list)
        # 4. Check Section Clashes
        sec_slot_map = defaultdict(list)
        # 5. Check Batch Clashes
        batch_slot_map = defaultdict(list)

        for idx, entry in enumerate(self.entries):
            slot_id = entry.get("time_slot_id")
            fac_id = entry.get("faculty_id")
            co_fac_ids = entry.get("co_faculty_ids", [])
            sec_id = entry.get("section_id")
            sub_id = entry.get("subject_id")
            room_id = entry.get("classroom_id")
            lab_id = entry.get("laboratory_id")
            batch_id = entry.get("lab_batch_id")

            # A. Faculty check
            if fac_id:
                fac_slot_map[(fac_id, slot_id)].append((idx, "primary", entry))
            for co_f in co_fac_ids:
                fac_slot_map[(co_f, slot_id)].append((idx, "co_teacher", entry))

            # B. Room check
            if room_id:
                room_slot_map[(room_id, slot_id)].append((idx, entry))

            # C. Lab check
            if lab_id:
                lab_slot_map[(lab_id, slot_id)].append((idx, entry))

            # D. Section check
            if sec_id and entry.get("entry_type") != "lab":
                sec_slot_map[(sec_id, slot_id)].append((idx, entry))

            # E. Batch check
            if batch_id:
                batch_slot_map[(batch_id, slot_id)].append((idx, entry))

            # F. Check Room Capacity
            if room_id and sec_id:
                room = self.classrooms.get(room_id)
                sec = self.sections.get(sec_id)
                if room and sec and sec.get("student_strength", 0) > room.get("capacity", 0):
                    conflicts.append({
                        "id": str(uuid.uuid4()),
                        "severity": "error",
                        "conflict_type": "ROOM_CAPACITY_EXCEEDED",
                        "description": f"Classroom {room.get('room_code')} capacity ({room.get('capacity')}) is exceeded by section {sec.get('name')} strength ({sec.get('student_strength')}).",
                        "related_entity_id": room_id,
                        "details": {"room": room, "section": sec, "entry_index": idx}
                    })

            # G. Check Lab Capacity
            if lab_id and batch_id:
                lab = self.labs.get(lab_id)
                batch = self.batches.get(batch_id)
                if lab and batch and batch.get("student_count", 0) > lab.get("student_capacity", 0):
                    conflicts.append({
                        "id": str(uuid.uuid4()),
                        "severity": "error",
                        "conflict_type": "LAB_CAPACITY_EXCEEDED",
                        "description": f"Laboratory {lab.get('lab_code')} capacity ({lab.get('student_capacity')}) is exceeded by batch {batch.get('batch_name')} count ({batch.get('student_count')}).",
                        "related_entity_id": lab_id,
                        "details": {"lab": lab, "batch": batch, "entry_index": idx}
                    })

            # H. Check Faculty Qualification
            if fac_id and sub_id:
                if not self.qualifications.get((fac_id, sub_id), True):
                    fac = self.faculty.get(fac_id, {})
                    sub = self.subjects.get(sub_id, {})
                    conflicts.append({
                        "id": str(uuid.uuid4()),
                        "severity": "error",
                        "conflict_type": "UNQUALIFIED_FACULTY",
                        "description": f"Faculty {fac.get('full_name')} is not marked qualified to teach subject {sub.get('subject_code')} ({sub.get('subject_name')}).",
                        "related_entity_id": fac_id,
                        "details": {"faculty": fac, "subject": sub, "entry_index": idx}
                    })

            # I. Check Availability
            if fac_id and slot_id:
                if not self.availability.get("faculty", {}).get((fac_id, slot_id), True):
                    fac = self.faculty.get(fac_id, {})
                    conflicts.append({
                        "id": str(uuid.uuid4()),
                        "severity": "error",
                        "conflict_type": "FACULTY_UNAVAILABLE",
                        "description": f"Faculty {fac.get('full_name')} is marked unavailable during time slot {slot_id}.",
                        "related_entity_id": fac_id,
                        "details": {"faculty": fac, "slot_id": slot_id, "entry_index": idx}
                    })

        # Process Faculty Clashes
        for (fac_id, slot_id), occurrences in fac_slot_map.items():
            if len(occurrences) > 1:
                fac = self.faculty.get(fac_id, {})
                conflicts.append({
                    "id": str(uuid.uuid4()),
                    "severity": "error",
                    "conflict_type": "FACULTY_CLASH",
                    "description": f"Faculty {fac.get('full_name')} ({fac.get('employee_id')}) is scheduled for {len(occurrences)} simultaneous classes at time slot {slot_id}.",
                    "related_entity_id": fac_id,
                    "details": {"occurrences": occurrences, "slot_id": slot_id}
                })

        # Process Classroom Clashes
        for (room_id, slot_id), occurrences in room_slot_map.items():
            if len(occurrences) > 1:
                room = self.classrooms.get(room_id, {})
                conflicts.append({
                    "id": str(uuid.uuid4()),
                    "severity": "error",
                    "conflict_type": "CLASSROOM_CLASH",
                    "description": f"Classroom {room.get('room_code')} is booked for {len(occurrences)} simultaneous sessions at time slot {slot_id}.",
                    "related_entity_id": room_id,
                    "details": {"occurrences": occurrences, "slot_id": slot_id}
                })

        # Process Lab Clashes
        for (lab_id, slot_id), occurrences in lab_slot_map.items():
            if len(occurrences) > 1:
                lab = self.labs.get(lab_id, {})
                conflicts.append({
                    "id": str(uuid.uuid4()),
                    "severity": "error",
                    "conflict_type": "LABORATORY_CLASH",
                    "description": f"Laboratory {lab.get('lab_code')} is booked for {len(occurrences)} simultaneous practicals at time slot {slot_id}.",
                    "related_entity_id": lab_id,
                    "details": {"occurrences": occurrences, "slot_id": slot_id}
                })

        # Process Section Clashes
        for (sec_id, slot_id), occurrences in sec_slot_map.items():
            if len(occurrences) > 1:
                sec = self.sections.get(sec_id, {})
                conflicts.append({
                    "id": str(uuid.uuid4()),
                    "severity": "error",
                    "conflict_type": "SECTION_CLASH",
                    "description": f"Section {sec.get('name')} is assigned {len(occurrences)} simultaneous lectures at time slot {slot_id}.",
                    "related_entity_id": sec_id,
                    "details": {"occurrences": occurrences, "slot_id": slot_id}
                })

        # Process Batch Clashes
        for (b_id, slot_id), occurrences in batch_slot_map.items():
            if len(occurrences) > 1:
                batch = self.batches.get(b_id, {})
                conflicts.append({
                    "id": str(uuid.uuid4()),
                    "severity": "error",
                    "conflict_type": "BATCH_CLASH",
                    "description": f"Batch {batch.get('batch_name')} is scheduled for {len(occurrences)} simultaneous lab sessions at time slot {slot_id}.",
                    "related_entity_id": b_id,
                    "details": {"occurrences": occurrences, "slot_id": slot_id}
                })

        return conflicts
