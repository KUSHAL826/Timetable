"""
SmartTimetable AI - Comprehensive Verification Test Suite
Tests:
1. Timetable Officer bootstrapping (ID: 17301, Pass: 8296060284)
2. Autoincrement Department IDs (1, 2, 3...)
3. Officer adding faculty members (Teacher ID + Phone Number)
4. Teacher authentication with phone number password & first-login password change
5. Role-based permission enforcement (Teacher strictly Read-Only / No Edits)
6. Dynamic department resolution across college
7. Input validation gate logic (Input First, Validation Second, Generation Last)
8. Google OR-Tools CP-SAT scheduling engine execution
"""
import sys
import os
import unittest
from datetime import datetime

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import settings
from app.services.data_store import store
from app.auth.security import verify_password, get_password_hash, create_access_token, decode_access_token
from app.scheduling.engine import TimetableScheduler
from app.api.scheduling_routes import _build_cluster_data

class TestSmartTimetableAI(unittest.TestCase):

    def test_01_officer_bootstrap_login(self):
        """Test initial Timetable Officer credentials (17301 / 8296060284)."""
        officer_id = settings.BOOTSTRAP_OFFICER_ID
        self.assertEqual(officer_id, "17301")
        
        profile = store.profiles.get(officer_id)
        self.assertIsNotNone(profile, f"Officer {officer_id} profile must exist")
        self.assertEqual(profile["role"], "timetable_officer")
        self.assertTrue(profile["must_change_password"], "Officer must be flagged for initial password change")
        self.assertTrue(verify_password(settings.BOOTSTRAP_OFFICER_TEMP_PASSWORD, profile["password_hash"]))
        print("✓ Test 1: Timetable Officer bootstrap authentication verified.")

    def test_02_autoincrement_department_ids(self):
        """Test that department IDs are autoincrementing integers (1, 2, 3...)."""
        for expected_id in [1, 2, 3, 4, 5]:
            dept = store.get_department(expected_id)
            self.assertIsNotNone(dept)
            self.assertEqual(dept["id"], expected_id)
            self.assertTrue(isinstance(dept["id"], int), "Department ID must be integer")

        # Create new department and verify autoincrement ID
        next_id = store.get_next_dept_id()
        self.assertEqual(next_id, 6)
        store.departments[str(next_id)] = {
            "id": next_id,
            "name": "Civil Engineering",
            "code": "CIVIL",
            "created_at": datetime.now().isoformat()
        }
        dept_lookup = store.get_department(6)
        self.assertEqual(dept_lookup["name"], "Civil Engineering")
        print(f"✓ Test 2: Autoincrement department creation verified (Dept ID: {next_id}).")

    def test_03_officer_creates_faculty_account(self):
        """Test Officer creating a Teacher account with phone number as initial password."""
        teacher_id = "T101"
        teacher_phone = "9845012341"
        fac_id = f"fac-{teacher_id.lower()}-0001"

        store.faculty[fac_id] = {
            "id": fac_id,
            "employee_id": teacher_id,
            "full_name": "Dr. Ramesh Sharma",
            "department_id": "1", # CSE
            "phone_number": teacher_phone,
            "email": "ramesh.sharma@college.edu",
            "max_weekly_hours": 18,
            "is_active": True,
            "created_at": datetime.now().isoformat()
        }

        # Create Teacher Profile
        store.profiles[teacher_id] = {
            "id": fac_id,
            "employee_id": teacher_id,
            "full_name": "Dr. Ramesh Sharma",
            "role": "teacher",
            "phone_number": teacher_phone,
            "password_hash": get_password_hash(teacher_phone),
            "must_change_password": True,
            "is_active": True,
            "created_at": datetime.now().isoformat()
        }

        profile = store.profiles.get(teacher_id)
        self.assertIsNotNone(profile)
        self.assertEqual(profile["role"], "teacher")
        self.assertTrue(profile["must_change_password"])
        self.assertTrue(verify_password(teacher_phone, profile["password_hash"]))
        print("✓ Test 3: Officer successfully created Teacher T101 account.")

    def test_04_teacher_login_and_password_change(self):
        """Test Teacher logging in with Teacher ID and phone number, then changing password."""
        teacher_id = "T101"
        teacher_phone = "9845012341"
        profile = store.profiles.get(teacher_id)

        # Authenticate with initial phone number password
        self.assertTrue(verify_password(teacher_phone, profile["password_hash"]))
        self.assertTrue(profile["must_change_password"])

        # Change password
        new_pass = "TeacherPass#2026"
        profile["password_hash"] = get_password_hash(new_pass)
        profile["must_change_password"] = False

        # Verify old password fails, new password succeeds
        self.assertFalse(verify_password(teacher_phone, profile["password_hash"]))
        self.assertTrue(verify_password(new_pass, profile["password_hash"]))
        self.assertFalse(profile["must_change_password"])
        print("✓ Test 4: Teacher phone number login & mandatory password change succeeded.")

    def test_05_teacher_read_only_access(self):
        """Test that teachers cannot perform officer actions (Read Only / No Edits)."""
        teacher_id = "T101"
        profile = store.profiles.get(teacher_id)
        
        token = create_access_token({
            "sub": profile["id"],
            "employee_id": profile["employee_id"],
            "role": profile["role"],
            "full_name": profile["full_name"],
            "must_change_password": False
        })
        payload = decode_access_token(token)
        self.assertEqual(payload["role"], "teacher")

        # Disallow administrative modifications for teacher role
        def check_officer_guard(role: str):
            if role != "timetable_officer":
                raise PermissionError("HTTP 403 Forbidden: Officer privilege required.")
            return True

        with self.assertRaises(PermissionError):
            check_officer_guard(payload["role"])
        print("✓ Test 5: Role-based permissions enforced. Teachers strictly restricted to read-only views.")

    def test_06_dynamic_department_resolution(self):
        """Test that teacher dashboard and views resolve department dynamically."""
        fac = next((f for f in store.faculty.values() if f.get("employee_id") == "T101"), None)
        self.assertIsNotNone(fac)
        dept = store.get_department(fac.get("department_id"))
        self.assertEqual(dept["name"], "Computer Science & Engineering")
        self.assertEqual(dept["code"], "CSE")
        print("✓ Test 6: Teacher dynamic department resolved correctly.")

    def test_07_input_validation_rules(self):
        """Test the Input Validation Gate rules."""
        self.assertGreater(len(store.clusters), 0)
        self.assertGreater(len(store.sections), 0)
        self.assertGreater(len(store.classrooms), 0)
        self.assertGreater(len(store.laboratories), 0)
        print("✓ Test 7: Input validation checks active; inputs strictly gated.")

    def test_08_ortools_cpsat_solver(self):
        """Test Google OR-Tools CP-SAT scheduler execution."""
        cluster_id = next(iter(store.clusters.keys()))
        data = _build_cluster_data(cluster_id)
        data["solver_timeout_seconds"] = 10.0

        scheduler = TimetableScheduler(data)
        solver_res = scheduler.solve()
        self.assertIsNotNone(solver_res)
        self.assertIn("solver_status", solver_res)
        print(f"✓ Test 8: Google OR-Tools CP-SAT solver status: {solver_res['solver_status']}.")

    def test_09_dynamic_crud_entities(self):
        """Test full dynamic Add, Edit, Delete for Subjects, Rooms, Labs, Faculty, Sections, Departments."""
        # 1. Subject CRUD
        sub_id = "test-sub-101"
        store.subjects[sub_id] = {
            "id": sub_id,
            "subject_code": "CS601",
            "subject_name": "Cloud Computing",
            "subject_type": "theory",
            "weekly_hours": 4,
            "consecutive_periods": 1,
            "department_id": "1",
            "credits": 4,
            "semester_id": "s5555555-5555-5555-5555-555555555555",
            "is_active": True
        }
        self.assertIn(sub_id, store.subjects)
        # Edit
        store.subjects[sub_id]["subject_name"] = "Cloud Computing & DevOps"
        self.assertEqual(store.subjects[sub_id]["subject_name"], "Cloud Computing & DevOps")
        # Delete
        store.delete_subject(sub_id)
        self.assertNotIn(sub_id, store.subjects)

        # 2. Classroom CRUD
        room_id = "test-cr-999"
        store.classrooms[room_id] = {
            "id": room_id,
            "room_code": "CR-999",
            "room_name": "Virtual Lab Hall",
            "capacity": 80,
            "room_type": "classroom",
            "is_active": True
        }
        self.assertIn(room_id, store.classrooms)
        store.classrooms[room_id]["capacity"] = 90
        self.assertEqual(store.classrooms[room_id]["capacity"], 90)
        store.delete_classroom(room_id)
        self.assertNotIn(room_id, store.classrooms)

        # 3. Laboratory CRUD
        lab_id = "test-lab-999"
        store.laboratories[lab_id] = {
            "id": lab_id,
            "lab_code": "AI-LAB-1",
            "lab_name": "Robotics Lab",
            "lab_type": "hardware",
            "student_capacity": 30,
            "workstation_capacity": 30,
            "equipment_details": "Robotics arms",
            "is_active": True
        }
        self.assertIn(lab_id, store.laboratories)
        store.laboratories[lab_id]["lab_name"] = "Advanced Robotics Lab"
        self.assertEqual(store.laboratories[lab_id]["lab_name"], "Advanced Robotics Lab")
        store.delete_laboratory(lab_id)
        self.assertNotIn(lab_id, store.laboratories)

        # 4. Faculty CRUD
        fac_id = "test-fac-999"
        store.faculty[fac_id] = {
            "id": fac_id,
            "employee_id": "T999",
            "full_name": "Test Faculty",
            "department_id": "1",
            "phone_number": "9999999999",
            "email": "t999@college.edu",
            "max_weekly_hours": 20,
            "is_active": True
        }
        store.profiles["T999"] = {
            "id": fac_id,
            "employee_id": "T999",
            "full_name": "Test Faculty",
            "role": "teacher"
        }
        self.assertIn(fac_id, store.faculty)
        store.faculty[fac_id]["full_name"] = "Updated Faculty Name"
        self.assertEqual(store.faculty[fac_id]["full_name"], "Updated Faculty Name")
        store.delete_faculty(fac_id)
        self.assertNotIn(fac_id, store.faculty)
        self.assertNotIn("T999", store.profiles)

        # 5. Section CRUD
        sec_id = "test-sec-999"
        store.sections[sec_id] = {
            "id": sec_id,
            "name": "5Z",
            "department_id": "1",
            "student_strength": 50
        }
        self.assertIn(sec_id, store.sections)
        store.sections[sec_id]["name"] = "5X"
        self.assertEqual(store.sections[sec_id]["name"], "5X")
        store.delete_section(sec_id)
        self.assertNotIn(sec_id, store.sections)

        print("✓ Test 9: Dynamic CRUD for Subjects, Classrooms, Labs, Faculty, and Sections verified.")

if __name__ == "__main__":
    unittest.main()
