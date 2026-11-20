import os
import json
import uuid
import copy
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from app.config import settings
from app.auth.security import get_password_hash

class DataStore:
    """
    Institutional Data Store for SmartTimetable AI.
    Pure Python persistence layer seeded with the initial Timetable Officer credentials
    and multi-department college academic structure with AUTOINCREMENT department IDs.
    Faculties are added dynamically by the Officer.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DataStore, cls).__new__(cls)
            cls._instance._init_store()
        return cls._instance

    def _init_store(self):
        # Autoincrement sequence counter for departments
        self._dept_counter: int = 0

        self.profiles: Dict[str, Dict[str, Any]] = {}
        self.departments: Dict[str, Dict[str, Any]] = {}
        self.academic_years: Dict[str, Dict[str, Any]] = {}
        self.semesters: Dict[str, Dict[str, Any]] = {}
        self.clusters: Dict[str, Dict[str, Any]] = {}
        self.sections: Dict[str, Dict[str, Any]] = {}
        self.cluster_sections: List[Dict[str, str]] = []
        self.faculty: Dict[str, Dict[str, Any]] = {}
        self.cluster_faculty: List[Dict[str, str]] = []
        self.subjects: Dict[str, Dict[str, Any]] = {}
        self.faculty_subjects: Dict[str, Dict[str, Any]] = {} # key: f"{fac_id}_{sub_id}"
        self.section_subjects: Dict[str, Dict[str, Any]] = {}
        self.subject_allocations: Dict[str, Dict[str, Any]] = {}
        self.time_slots: Dict[str, Dict[str, Any]] = {}
        self.classrooms: Dict[str, Dict[str, Any]] = {}
        self.laboratories: Dict[str, Dict[str, Any]] = {}
        self.lab_subjects: List[Dict[str, str]] = []
        self.lab_staffing_requirements: Dict[str, Dict[str, Any]] = {}
        self.lab_co_teachers: List[Dict[str, str]] = []
        self.lab_batches: Dict[str, Dict[str, Any]] = {}
        self.elective_groups: Dict[str, Dict[str, Any]] = {}
        self.elective_options: Dict[str, Dict[str, Any]] = {}
        self.student_elective_counts: Dict[str, Dict[str, Any]] = {}
        self.faculty_availability: Dict[str, bool] = {} # key: f"{fac_id}_{slot_id}"
        self.section_availability: Dict[str, bool] = {} # key: f"{sec_id}_{slot_id}"
        self.classroom_availability: Dict[str, bool] = {} # key: f"{room_id}_{slot_id}"
        self.lab_availability: Dict[str, bool] = {} # key: f"{lab_id}_{slot_id}"
        self.timetable_generations: Dict[str, Dict[str, Any]] = {}
        self.timetable_entries: Dict[str, Dict[str, Any]] = {}
        self.timetable_approvals: Dict[str, Dict[str, Any]] = {}
        self.generation_conflicts: Dict[str, Dict[str, Any]] = {}
        self.audit_logs: List[Dict[str, Any]] = []

        self._seed_default_data()

    def get_next_dept_id(self) -> int:
        """Generates an autoincrement integer department ID."""
        self._dept_counter += 1
        return self._dept_counter

    def get_department(self, dept_id: Any) -> Dict[str, Any]:
        """Safely fetch department by integer or string autoincrement ID."""
        if dept_id is None:
            return {}
        return self.departments.get(str(dept_id)) or self.departments.get(dept_id) or {}

    def _seed_default_data(self):
        # 1. BOOTSTRAP ONLY THE TIMETABLE OFFICER CREDENTIAL
        # Officer ID: 17301
        # Initial Temporary Password: 8296060284
        officer_id = settings.BOOTSTRAP_OFFICER_ID
        self.profiles[officer_id] = {
            "id": "prof-officer-0000-0000-000000000001",
            "employee_id": officer_id,
            "full_name": "Chief Timetable Officer",
            "role": "timetable_officer",
            "phone_number": "8296060284",
            "password_hash": get_password_hash(settings.BOOTSTRAP_OFFICER_TEMP_PASSWORD),
            "must_change_password": True,
            "is_active": True,
            "created_at": datetime.utcnow().isoformat()
        }

        # 2. Institutional College Departments (Autoincrementing IDs: 1, 2, 3...)
        self._dept_counter = 0
        dept_defs = [
            ("Computer Science & Engineering", "CSE"),
            ("Information Science & Engineering", "ISE"),
            ("Electronics & Communication Engineering", "ECE"),
            ("Artificial Intelligence & Machine Learning", "AIML"),
            ("Mechanical Engineering", "MECH")
        ]
        created_dept_ids = []
        for d_name, d_code in dept_defs:
            autoincrement_id = self.get_next_dept_id()
            str_id = str(autoincrement_id)
            self.departments[str_id] = {
                "id": autoincrement_id,
                "name": d_name,
                "code": d_code,
                "created_at": datetime.utcnow().isoformat()
            }
            created_dept_ids.append(str_id)

        default_dept_id = created_dept_ids[0] # "1" (CSE)

        # 3. Academic Year & Semesters
        ay_id = "a1111111-1111-1111-1111-111111111111"
        self.academic_years[ay_id] = {
            "id": ay_id,
            "name": "2026-2027",
            "start_date": "2026-08-01",
            "end_date": "2027-05-31",
            "is_active": True
        }
        sem_id = "s5555555-5555-5555-5555-555555555555"
        self.semesters[sem_id] = {
            "id": sem_id,
            "semester_number": 5,
            "academic_year_id": ay_id,
            "start_date": "2026-08-01",
            "end_date": "2026-12-31"
        }

        # 4. Clusters (Department Mapped with Autoincrement Department ID)
        cluster_id = "c1111111-1111-1111-1111-111111111111"
        self.clusters[cluster_id] = {
            "id": cluster_id,
            "name": "Cluster 1 - CSE 5th Sem",
            "department_id": default_dept_id,
            "semester_id": sem_id,
            "description": "Primary CSE 5th semester cluster",
            "is_active": True,
            "section_ids": [
                "sec-5a01-0000-0000-000000000001",
                "sec-5b02-0000-0000-000000000002"
            ]
        }

        # 5. Sections (Department Mapped)
        for s_num, s_name in enumerate(["5A", "5B"], 1):
            s_id = f"sec-5{s_name.lower()}0{s_num}-0000-0000-00000000000{s_num}"
            self.sections[s_id] = {
                "id": s_id,
                "name": s_name,
                "department_id": default_dept_id,
                "semester_id": sem_id,
                "student_strength": 60,
                "cluster_id": cluster_id
            }
            self.cluster_sections.append({"cluster_id": cluster_id, "section_id": s_id})

            # Batches for each section (e.g., Batch 1: 30, Batch 2: 30)
            b1_id = f"btc-5{s_name.lower()}01-0000-0000-00000000000{s_num}"
            b2_id = f"btc-5{s_name.lower()}02-0000-0000-00000000000{s_num}"
            self.lab_batches[b1_id] = {
                "id": b1_id,
                "section_id": s_id,
                "batch_name": f"Batch {s_name}1",
                "student_count": 30
            }
            self.lab_batches[b2_id] = {
                "id": b2_id,
                "section_id": s_id,
                "batch_name": f"Batch {s_name}2",
                "student_count": 30
            }

        # 6. Classrooms
        for i in range(101, 105):
            r_id = f"cr-0{i}-0000-0000-00000000000{i-100}"
            self.classrooms[r_id] = {
                "id": r_id,
                "room_code": f"CR-{i}",
                "room_name": f"Lecture Hall {i}",
                "capacity": 75 if i <= 103 else 85,
                "room_type": "classroom",
                "is_active": True
            }

        # 7. Laboratories
        lab1_id = "lab-0001-0000-0000-000000000001"
        self.laboratories[lab1_id] = {
            "id": lab1_id,
            "lab_code": "CS-LAB-1",
            "lab_name": "Computer Networks Lab",
            "lab_type": "networking",
            "student_capacity": 35,
            "workstation_capacity": 35,
            "equipment_details": "40 High-speed Cisco switches, routers, and Linux workstations",
            "is_active": True
        }
        lab2_id = "lab-0002-0000-0000-000000000002"
        self.laboratories[lab2_id] = {
            "id": lab2_id,
            "lab_code": "CS-LAB-2",
            "lab_name": "Web Technology Lab",
            "lab_type": "software",
            "student_capacity": 35,
            "workstation_capacity": 35,
            "equipment_details": "40 Dual-boot Core i7 workstations with Cloud dev environments",
            "is_active": True
        }

        # 8. Subjects (Department Mapped)
        sub_cn_id = "sub-0501-0000-0000-000000000001"
        self.subjects[sub_cn_id] = {
            "id": sub_cn_id,
            "subject_code": "CS501",
            "subject_name": "Computer Networks",
            "subject_type": "theory",
            "weekly_hours": 4,
            "consecutive_periods": 1,
            "department_id": default_dept_id,
            "credits": 4,
            "semester_id": sem_id,
            "is_active": True
        }
        sub_dbms_id = "sub-0502-0000-0000-000000000002"
        self.subjects[sub_dbms_id] = {
            "id": sub_dbms_id,
            "subject_code": "CS502",
            "subject_name": "Database Management Systems",
            "subject_type": "theory",
            "weekly_hours": 4,
            "consecutive_periods": 1,
            "department_id": default_dept_id,
            "credits": 4,
            "semester_id": sem_id,
            "is_active": True
        }
        sub_cn_lab_id = "sub-0511-0000-0000-000000000011"
        self.subjects[sub_cn_lab_id] = {
            "id": sub_cn_lab_id,
            "subject_code": "CSL51",
            "subject_name": "Computer Networks Laboratory",
            "subject_type": "practical",
            "weekly_hours": 3,
            "consecutive_periods": 3,
            "department_id": default_dept_id,
            "credits": 2,
            "semester_id": sem_id,
            "is_active": True
        }

        # 9. Time Slots (Monday to Friday, 6 periods)
        slot_counter = 1
        for d in range(1, 6): # Mon-Fri
            timings = [
                ("09:00:00", "10:00:00"),
                ("10:00:00", "11:00:00"),
                ("11:15:00", "12:15:00"),
                ("12:15:00", "13:15:00"),
                ("14:00:00", "15:00:00"),
                ("15:00:00", "16:00:00")
            ]
            for p, (st, et) in enumerate(timings, 1):
                slot_id = f"ts-000{slot_counter:02d}-0000-0000-000000000000"
                self.time_slots[slot_id] = {
                    "id": slot_id,
                    "day_of_week": d,
                    "period_number": p,
                    "start_time": st,
                    "end_time": et,
                    "slot_type": "class",
                    "is_schedulable": True
                }
                slot_counter += 1

        # 10. Availability Grid Initialization
        for s_id in self.time_slots.keys():
            for sec_id in self.sections.keys():
                self.section_availability[f"{sec_id}_{s_id}"] = True
            for r_id in self.classrooms.keys():
                self.classroom_availability[f"{r_id}_{s_id}"] = True
            for l_id in self.laboratories.keys():
                self.lab_availability[f"{l_id}_{s_id}"] = True

store = DataStore()
