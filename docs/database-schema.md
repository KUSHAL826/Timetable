# SmartTimetable AI — Database Schema Reference

The database runs on Supabase PostgreSQL with Row Level Security (RLS) enabled across all public tables.

## Entity Relationship Overview

### 1. User Management & Authentication
- `public.profiles`: Extends `auth.users` with `employee_id`, `role` (`timetable_officer`, `teacher`), `phone_number`, `must_change_password`, `is_active`.
- `public.audit_logs`: Detailed tracking of administrative actions and timetable changes.

### 2. Academic Core
- `public.departments`: Academic departments (CSE, ISE, ECE, MECH, etc.).
- `public.academic_years`: Academic calendar intervals (e.g. 2026-2027) with active state flags.
- `public.semesters`: Semester records linked to academic years.
- `public.clusters`: Groups of sections scheduled concurrently.
- `public.sections`: Student sections with class strength and cluster mappings.
- `public.cluster_sections`: M:M link between clusters and sections.

### 3. Faculty & Subject Allocations
- `public.faculty`: Faculty roster with department, maximum weekly hours, and contact details.
- `public.cluster_faculty`: Faculty participating in a specific cluster.
- `public.subjects`: Theory, practical, and elective subject definitions.
- `public.faculty_subjects`: Qualification mapping ensuring faculty are qualified to teach allocated subjects.
- `public.section_subjects`: Curriculum requirements per section.
- `public.subject_allocations`: Primary and co-teacher assignments per section subject.

### 4. Infrastructure & Capacities
- `public.classrooms`: Room codes, types, and seating capacity.
- `public.laboratories`: Lab codes, student capacity, and workstation capacity.
- `public.lab_subjects`: Permitted practical subjects for each laboratory.
- `public.lab_staffing_requirements`: Configured primary faculty, required co-teacher count, and consecutive period requirements.
- `public.lab_co_teachers`: Assigned co-teachers for each lab requirement.
- `public.lab_batches`: Sub-section groups (e.g. Batch 1: 30, Batch 2: 30) for concurrent lab scheduling.

### 5. Professional Electives
- `public.elective_groups`: Elective clusters operating within synchronized time slots.
- `public.elective_options`: Specific subjects offered within an elective block with designated classrooms.
- `public.student_elective_counts`: Student counts registered for each elective option per source section.

### 6. Availability Matrices
- `public.time_slots`: Weekly timetable schedule grid (day, period, start time, end time, slot type).
- `public.faculty_availability`: Slot availability for each teacher.
- `public.section_availability`: Slot availability for each section.
- `public.classroom_availability`: Slot availability for each lecture hall.
- `public.lab_availability`: Slot availability for each lab.

### 7. Timetable Outputs & Lifecycle
- `public.timetable_generations`: Solver execution runs, status lifecycle (`draft`, `generated`, `validated`, `submitted`, `approved`, `published`), input snapshots, diagnostics.
- `public.timetable_entries`: Scheduled period assignments linking section, subject, faculty, room/lab, batch, and time slot.
- `public.timetable_approvals`: Multi-step approval records with submitter, approver, and decision timestamps.
- `public.generation_conflicts`: Detailed solver diagnostics and manual editing conflict reports.
- `public.resource_reservations`: Ad-hoc reservations preventing clashes.
