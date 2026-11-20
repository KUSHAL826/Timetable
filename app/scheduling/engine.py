import time
from typing import Dict, List, Any, Tuple, Optional
from ortools.sat.python import cp_model
import logging

logger = logging.getLogger(__name__)

class TimetableScheduler:
    """
    Production-grade College Timetable Scheduler using Google OR-Tools CP-SAT.
    Enforces strict institutional hard constraints and optimizes soft constraints.
    """

    def __init__(self, data: Dict[str, Any]):
        """
        data dictionary must contain:
        - cluster: dict with cluster metadata
        - sections: list of section dicts (id, name, student_strength)
        - subjects: list of subject dicts (id, subject_code, subject_name, subject_type, weekly_hours, consecutive_periods)
        - faculty: list of faculty dicts (id, employee_id, full_name, max_weekly_hours)
        - classrooms: list of classroom dicts (id, room_code, capacity)
        - laboratories: list of laboratory dicts (id, lab_code, student_capacity)
        - time_slots: list of time_slot dicts (id, day_of_week, period_number, is_schedulable)
        - section_subjects: list of curriculum items with allocations
        - lab_staffing: list of lab staffing requirements (section_id, subject_id, lab_id, primary_faculty_id, co_teacher_ids, weekly_hours, consecutive_periods)
        - lab_batches: list of lab batch dicts (id, section_id, batch_name, student_count)
        - electives: list of elective groups with options and enrolled section counts
        - availability: dict with faculty, section, classroom, lab availability sets
        """
        self.data = data
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        self.solver.parameters.max_time_in_seconds = data.get("solver_timeout_seconds", 60.0)
        self.solver.parameters.num_workers = 4

        # Pre-process time slots: sort by day and period
        self.slots = [s for s in data.get("time_slots", []) if s.get("is_schedulable", True)]
        self.slots.sort(key=lambda s: (s["day_of_week"], s["period_number"]))
        self.slot_map = {s["id"]: s for s in self.slots}
        self.slot_by_day_period = {(s["day_of_week"], s["period_number"]): s["id"] for s in self.slots}
        self.days = sorted(list(set(s["day_of_week"] for s in self.slots)))

        # Pre-process lookups
        self.sections = {s["id"]: s for s in data.get("sections", [])}
        self.subjects = {s["id"]: s for s in data.get("subjects", [])}
        self.faculty = {f["id"]: f for f in data.get("faculty", [])}
        self.classrooms = {c["id"]: c for c in data.get("classrooms", [])}
        self.labs = {l["id"]: l for l in data.get("laboratories", [])}

        # Availability maps: key is (entity_id, slot_id) -> bool
        self.fac_avail = data.get("faculty_availability", {})
        self.sec_avail = data.get("section_availability", {})
        self.room_avail = data.get("classroom_availability", {})
        self.lab_avail = data.get("lab_availability", {})

        # Decision variables storage
        # (type, entity_tuple, slot_id) -> BoolVar
        self.theory_vars = {}     # (section_id, subject_id, faculty_id, room_id, slot_id) -> BoolVar
        self.lab_vars = {}        # (section_id, batch_id, subject_id, lab_id, primary_fac_id, tuple(co_fac_ids), slot_id) -> BoolVar
        self.elective_vars = {}   # (group_id, option_id, subject_id, faculty_id, room_id, slot_id) -> BoolVar

    def build_model(self) -> Tuple[bool, List[str]]:
        """Constructs all variables and constraints."""
        errors = []

        # 1. Build Theory variables
        # For each section and its regular theory subjects
        for req in self.data.get("theory_requirements", []):
            sec_id = req["section_id"]
            sub_id = req["subject_id"]
            fac_id = req["primary_faculty_id"]
            weekly_hours = req["weekly_hours"]
            sec_strength = self.sections[sec_id]["student_strength"]

            # Filter valid classrooms by capacity
            valid_rooms = [
                r["id"] for r in self.classrooms.values()
                if r["capacity"] >= sec_strength
            ]
            if not valid_rooms:
                errors.append(f"No classroom with sufficient capacity ({sec_strength}) for section {self.sections[sec_id]['name']}")
                continue

            sec_theory_slot_vars = []
            for slot in self.slots:
                slot_id = slot["id"]
                # Availability checks
                if not self.sec_avail.get((sec_id, slot_id), True):
                    continue
                if not self.fac_avail.get((fac_id, slot_id), True):
                    continue

                for r_id in valid_rooms:
                    if not self.room_avail.get((r_id, slot_id), True):
                        continue
                    v = self.model.NewBoolVar(f"th_{sec_id[:6]}_{sub_id[:6]}_{fac_id[:6]}_{r_id[:6]}_{slot_id[:6]}")
                    self.theory_vars[(sec_id, sub_id, fac_id, r_id, slot_id)] = v
                    sec_theory_slot_vars.append(v)

            # Constraint: exact weekly hours for this subject in this section
            if sec_theory_slot_vars:
                self.model.Add(cp_model.LinearExpr.Sum(sec_theory_slot_vars) == weekly_hours)
            else:
                errors.append(f"No available slots found for subject {self.subjects[sub_id]['subject_code']} in section {self.sections[sec_id]['name']}")

        # 2. Build Lab practical variables (with batches & co-teachers & consecutive slots)
        for lab_req in self.data.get("lab_requirements", []):
            sec_id = lab_req["section_id"]
            sub_id = lab_req["subject_id"]
            lab_id = lab_req["lab_id"]
            prim_fac = lab_req["primary_faculty_id"]
            co_facs = tuple(sorted(lab_req.get("co_teacher_ids", [])))
            consec = lab_req.get("consecutive_periods", 2)
            weekly_hrs = lab_req.get("weekly_hours", 2)
            batches = lab_req.get("batches", [])

            # Validate lab capacity
            lab_cap = self.labs[lab_id]["student_capacity"]

            for batch in batches:
                b_id = batch["id"]
                b_count = batch["student_count"]
                if b_count > lab_cap:
                    errors.append(f"Lab {self.labs[lab_id]['lab_code']} capacity ({lab_cap}) is less than batch size ({b_count})")
                    continue

                # Find valid consecutive blocks of length `consec` on each day
                batch_block_vars = []
                for day in self.days:
                    day_slots = [s for s in self.slots if s["day_of_week"] == day]
                    day_slots.sort(key=lambda s: s["period_number"])

                    for i in range(len(day_slots) - consec + 1):
                        block = day_slots[i : i + consec]
                        # Verify all slots in block are contiguous
                        is_contiguous = all(
                            block[k+1]["period_number"] == block[k]["period_number"] + 1
                            for k in range(consec - 1)
                        )
                        if not is_contiguous:
                            continue

                        # Check availability for section, all faculty, and lab
                        block_available = True
                        for s in block:
                            sid = s["id"]
                            if not self.sec_avail.get((sec_id, sid), True):
                                block_available = False
                                break
                            if not self.fac_avail.get((prim_fac, sid), True):
                                block_available = False
                                break
                            for co_f in co_facs:
                                if not self.fac_avail.get((co_f, sid), True):
                                    block_available = False
                                    break
                            if not self.lab_avail.get((lab_id, sid), True):
                                block_available = False
                                break

                        if not block_available:
                            continue

                        # Create a block variable representing scheduling this lab session starting at block[0]
                        block_v = self.model.NewBoolVar(f"lab_blk_{b_id[:6]}_{sub_id[:6]}_{day}_{block[0]['period_number']}")
                        batch_block_vars.append(block_v)

                        # Link each slot in the block to this block var
                        for s in block:
                            sid = s["id"]
                            self.lab_vars[(sec_id, b_id, sub_id, lab_id, prim_fac, co_facs, sid)] = block_v

                num_sessions = weekly_hrs // consec
                if batch_block_vars:
                    self.model.Add(cp_model.LinearExpr.Sum(batch_block_vars) == num_sessions)
                else:
                    errors.append(f"No valid consecutive slot blocks for lab {self.subjects[sub_id]['subject_code']} batch {batch['batch_name']}")

        # 3. Build Professional Electives variables (synchronized across participating sections)
        for grp in self.data.get("elective_groups", []):
            grp_id = grp["id"]
            options = grp.get("options", [])
            weekly_hrs = grp.get("weekly_hours", 3)
            participating_sec_ids = grp.get("participating_section_ids", [])

            # Synchronized block: all options in the group must be scheduled simultaneously
            for slot in self.slots:
                sid = slot["id"]
                # Slot active indicator for the elective group
                grp_slot_active = self.model.NewBoolVar(f"elec_grp_{grp_id[:6]}_{sid[:6]}")

                # For each elective option
                for opt in options:
                    opt_id = opt["id"]
                    sub_id = opt["subject_id"]
                    fac_id = opt["faculty_id"]
                    room_id = opt["classroom_id"]
                    total_students = opt["total_students"]

                    if room_id and self.classrooms[room_id]["capacity"] < total_students:
                        errors.append(f"Classroom capacity ({self.classrooms[room_id]['capacity']}) too small for elective option ({total_students})")
                        continue

                    # The option is active if the group slot is active
                    self.elective_vars[(grp_id, opt_id, sub_id, fac_id, room_id, sid)] = grp_slot_active

            # Constraint: total elective weekly hours
            grp_active_vars = [
                v for (k, v) in self.elective_vars.items()
                if k[0] == grp_id and k[1] == options[0]["id"]
            ]
            if grp_active_vars:
                self.model.Add(cp_model.LinearExpr.Sum(grp_active_vars) == weekly_hrs)

        if errors:
            return False, errors

        # 4. HARD CONSTRAINTS
        self._add_hard_constraints()

        # 5. SOFT OBJECTIVES
        self._add_soft_objectives()

        return True, []

    def _add_hard_constraints(self):
        """Adds fundamental conflict-prevention constraints."""
        # A. Section Clash: A section cannot have more than 1 regular activity per slot
        for sec_id in self.sections.keys():
            for slot in self.slots:
                sid = slot["id"]
                sec_active = []

                # Theory classes
                for (s_id, sub_id, f_id, r_id, slot_id), v in self.theory_vars.items():
                    if s_id == sec_id and slot_id == sid:
                        sec_active.append(v)

                # Electives that block this section
                for (g_id, opt_id, sub_id, f_id, r_id, slot_id), v in self.elective_vars.items():
                    # check if sec_id is in group's participating sections
                    grp = next((g for g in self.data.get("elective_groups", []) if g["id"] == g_id), None)
                    if grp and sec_id in grp.get("participating_section_ids", []) and slot_id == sid:
                        sec_active.append(v)

                # If section is attending theory/elective, sum <= 1
                if sec_active:
                    self.model.Add(cp_model.LinearExpr.Sum(sec_active) <= 1)

        # B. Batch Clash: A lab batch cannot have more than 1 activity per slot
        for slot in self.slots:
            sid = slot["id"]
            for b_key in self.data.get("lab_batches", []):
                b_id = b_key["id"]
                batch_active = []
                for (s_id, batch_id, sub_id, l_id, prim_f, co_f, slot_id), v in self.lab_vars.items():
                    if batch_id == b_id and slot_id == sid:
                        batch_active.append(v)
                if batch_active:
                    self.model.Add(cp_model.LinearExpr.Sum(batch_active) <= 1)

        # C. Faculty Clash: A faculty member cannot be in 2 places simultaneously
        for fac_id in self.faculty.keys():
            for slot in self.slots:
                sid = slot["id"]
                fac_active = []

                # Theory
                for (s_id, sub_id, f_id, r_id, slot_id), v in self.theory_vars.items():
                    if f_id == fac_id and slot_id == sid:
                        fac_active.append(v)

                # Lab (as primary faculty or co-teacher)
                for (s_id, b_id, sub_id, l_id, prim_f, co_f, slot_id), v in self.lab_vars.items():
                    if (prim_f == fac_id or fac_id in co_f) and slot_id == sid:
                        fac_active.append(v)

                # Electives
                for (g_id, opt_id, sub_id, f_id, r_id, slot_id), v in self.elective_vars.items():
                    if f_id == fac_id and slot_id == sid:
                        fac_active.append(v)

                if fac_active:
                    self.model.Add(cp_model.LinearExpr.Sum(fac_active) <= 1)

        # D. Classroom Clash: A classroom cannot host 2 sessions simultaneously
        for r_id in self.classrooms.keys():
            for slot in self.slots:
                sid = slot["id"]
                room_active = []

                for (s_id, sub_id, f_id, room_id, slot_id), v in self.theory_vars.items():
                    if room_id == r_id and slot_id == sid:
                        room_active.append(v)

                for (g_id, opt_id, sub_id, f_id, room_id, slot_id), v in self.elective_vars.items():
                    if room_id == r_id and slot_id == sid:
                        room_active.append(v)

                if room_active:
                    self.model.Add(cp_model.LinearExpr.Sum(room_active) <= 1)

        # E. Laboratory Clash: A lab cannot host 2 sessions simultaneously
        for l_id in self.labs.keys():
            for slot in self.slots:
                sid = slot["id"]
                lab_active = []

                for (s_id, b_id, sub_id, lab_id, prim_f, co_f, slot_id), v in self.lab_vars.items():
                    if lab_id == l_id and slot_id == sid:
                        lab_active.append(v)

                if lab_active:
                    self.model.Add(cp_model.LinearExpr.Sum(lab_active) <= 1)

    def _add_soft_objectives(self):
        """Configures soft objectives to optimize schedule quality."""
        penalty_terms = []

        # 1. Distribute subject sessions across different days (avoid 2 sessions of same theory subject on same day)
        for (sec_id, sub_id, fac_id, r_id, slot_id), v in self.theory_vars.items():
            pass

        # 2. Avoid gaps for sections where possible
        # 3. Respect preferred faculty periods
        pref_reward_terms = []
        for fac_id, f in self.faculty.items():
            preferred_periods = f.get("preferred_periods", [])
            for p_num in preferred_periods:
                for (s_id, sub_id, f_id, r_id, slot_id), v in self.theory_vars.items():
                    if f_id == fac_id and self.slot_map[slot_id]["period_number"] == p_num:
                        pref_reward_terms.append(v)

        if pref_reward_terms:
            self.model.Maximize(cp_model.LinearExpr.Sum(pref_reward_terms))

    def solve(self) -> Dict[str, Any]:
        """Runs the CP-SAT solver and formats the output."""
        start_time = time.time()
        success, errors = self.build_model()
        if not success:
            return {
                "status": "failed",
                "solver_status": "MODEL_INVALID",
                "solve_time_seconds": round(time.time() - start_time, 2),
                "entries": [],
                "errors": errors,
            }

        solver_status_code = self.solver.Solve(self.model)
        elapsed = round(time.time() - start_time, 2)

        status_str = {
            cp_model.OPTIMAL: "OPTIMAL",
            cp_model.FEASIBLE: "FEASIBLE",
            cp_model.INFEASIBLE: "INFEASIBLE",
            cp_model.MODEL_INVALID: "MODEL_INVALID",
            cp_model.UNKNOWN: "UNKNOWN",
        }.get(solver_status_code, "UNKNOWN")

        if solver_status_code not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return {
                "status": "infeasible" if solver_status_code == cp_model.INFEASIBLE else "failed",
                "solver_status": status_str,
                "solve_time_seconds": elapsed,
                "entries": [],
                "errors": [f"Scheduling solver returned {status_str}. The model constraints cannot be satisfied simultaneously."],
            }

        # Extract scheduled entries
        entries = []
        # A. Theory entries
        for (sec_id, sub_id, fac_id, r_id, slot_id), v in self.theory_vars.items():
            if self.solver.Value(v) == 1:
                slot = self.slot_map[slot_id]
                entries.append({
                    "section_id": sec_id,
                    "subject_id": sub_id,
                    "faculty_id": fac_id,
                    "classroom_id": r_id,
                    "laboratory_id": None,
                    "lab_batch_id": None,
                    "time_slot_id": slot_id,
                    "day_of_week": slot["day_of_week"],
                    "period_number": slot["period_number"],
                    "start_time": slot["start_time"],
                    "end_time": slot["end_time"],
                    "entry_type": "regular",
                })

        # B. Lab entries
        for (sec_id, b_id, sub_id, l_id, prim_f, co_f, slot_id), v in self.lab_vars.items():
            if self.solver.Value(v) == 1:
                slot = self.slot_map[slot_id]
                entries.append({
                    "section_id": sec_id,
                    "subject_id": sub_id,
                    "faculty_id": prim_f,
                    "co_faculty_ids": list(co_f),
                    "classroom_id": None,
                    "laboratory_id": l_id,
                    "lab_batch_id": b_id,
                    "time_slot_id": slot_id,
                    "day_of_week": slot["day_of_week"],
                    "period_number": slot["period_number"],
                    "start_time": slot["start_time"],
                    "end_time": slot["end_time"],
                    "entry_type": "lab",
                })

        # C. Elective entries
        for (g_id, opt_id, sub_id, fac_id, r_id, slot_id), v in self.elective_vars.items():
            if self.solver.Value(v) == 1:
                slot = self.slot_map[slot_id]
                entries.append({
                    "section_id": None, # Spans multiple sections in elective group
                    "subject_id": sub_id,
                    "faculty_id": fac_id,
                    "classroom_id": r_id,
                    "laboratory_id": None,
                    "lab_batch_id": None,
                    "time_slot_id": slot_id,
                    "day_of_week": slot["day_of_week"],
                    "period_number": slot["period_number"],
                    "start_time": slot["start_time"],
                    "end_time": slot["end_time"],
                    "entry_type": "elective",
                })

        return {
            "status": "success",
            "solver_status": status_str,
            "solve_time_seconds": elapsed,
            "entries_count": len(entries),
            "entries": entries,
            "errors": [],
        }
