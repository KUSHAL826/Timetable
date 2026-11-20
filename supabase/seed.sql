-- SMARTTIMETABLE AI: COMPREHENSIVE INSTITUTIONAL SEED DATA
-- Designed for realistic testing of all constraints:
-- Cluster scheduling, lab co-teachers, batches, electives, and availability.

-- 1. DEPARTMENTS (Autoincrementing IDs: 1, 2, 3...)
INSERT INTO public.departments (name, code) VALUES
('Computer Science & Engineering', 'CSE'),
('Information Science & Engineering', 'ISE'),
('Electronics & Communication Engineering', 'ECE')
ON CONFLICT (name) DO NOTHING;

-- 2. ACADEMIC YEARS
INSERT INTO public.academic_years (id, name, start_date, end_date, is_active) VALUES
('a1111111-1111-1111-1111-111111111111', '2026-2027', '2026-08-01', '2027-05-31', true)
ON CONFLICT (name) DO UPDATE SET is_active = true;

-- 3. SEMESTERS
INSERT INTO public.semesters (id, semester_number, academic_year_id, start_date, end_date) VALUES
('s5555555-5555-5555-5555-555555555555', 5, 'a1111111-1111-1111-1111-111111111111', '2026-08-01', '2026-12-31'),
('s6666666-6666-6666-6666-666666666666', 6, 'a1111111-1111-1111-1111-111111111111', '2027-01-15', '2027-05-31')
ON CONFLICT (semester_number, academic_year_id) DO NOTHING;

-- 4. CLUSTERS (Cluster 1: 5A, 5B, 5C; Cluster 2: 5D, 5E, 5F)
INSERT INTO public.clusters (id, name, department_id, semester_id, description, is_active) VALUES
('c1111111-1111-1111-1111-111111111111', 'Cluster 1 - CSE 5th Sem (A, B, C)', 1, 's5555555-5555-5555-5555-555555555555', 'Primary CSE morning cluster', true),
('c2222222-2222-2222-2222-222222222222', 'Cluster 2 - CSE 5th Sem (D, E, F)', 1, 's5555555-5555-5555-5555-555555555555', 'Secondary CSE cluster', true)
ON CONFLICT DO NOTHING;

-- 5. SECTIONS
INSERT INTO public.sections (id, name, department_id, semester_id, student_strength) VALUES
('sec-5a01-0000-0000-000000000001', '5A', 1, 's5555555-5555-5555-5555-555555555555', 60),
('sec-5b02-0000-0000-000000000002', '5B', 1, 's5555555-5555-5555-5555-555555555555', 60),
('sec-5c03-0000-0000-000000000003', '5C', 1, 's5555555-5555-5555-5555-555555555555', 60)
ON CONFLICT DO NOTHING;

-- Map Sections to Cluster 1
INSERT INTO public.cluster_sections (cluster_id, section_id) VALUES
('c1111111-1111-1111-1111-111111111111', 'sec-5a01-0000-0000-000000000001'),
('c1111111-1111-1111-1111-111111111111', 'sec-5b02-0000-0000-000000000002'),
('c1111111-1111-1111-1111-111111111111', 'sec-5c03-0000-0000-000000000003')
ON CONFLICT DO NOTHING;

-- 6. CLASSROOMS
INSERT INTO public.classrooms (id, room_code, room_name, capacity, room_type, is_active) VALUES
('cr-0101-0000-0000-000000000001', 'CR-101', 'Lecture Hall 101', 70, 'classroom', true),
('cr-0102-0000-0000-000000000002', 'CR-102', 'Lecture Hall 102', 70, 'classroom', true),
('cr-0103-0000-0000-000000000003', 'CR-103', 'Lecture Hall 103', 70, 'classroom', true),
('cr-0104-0000-0000-000000000004', 'CR-104', 'Special Lecture Hall 104', 85, 'classroom', true),
('cr-0105-0000-0000-000000000005', 'CR-105', 'Elective Hall 105', 80, 'classroom', true)
ON CONFLICT (room_code) DO NOTHING;

-- 7. LABORATORIES
INSERT INTO public.laboratories (id, lab_code, lab_name, lab_type, student_capacity, workstation_capacity, is_active) VALUES
('lab-0001-0000-0000-000000000001', 'CS-LAB-1', 'Computer Networks Lab', 'networking', 35, 35, true),
('lab-0002-0000-0000-000000000002', 'CS-LAB-2', 'Web Technology & Cloud Lab', 'software', 35, 35, true),
('lab-0003-0000-0000-000000000003', 'CS-LAB-3', 'Database Systems Lab', 'software', 40, 40, true)
ON CONFLICT (lab_code) DO NOTHING;

-- 8. SUBJECTS
INSERT INTO public.subjects (id, subject_code, subject_name, subject_type, weekly_hours, consecutive_periods, department_id, credits, semester_id) VALUES
('sub-0501-0000-0000-000000000001', 'CS501', 'Computer Networks', 'theory', 4, 1, 1, 4, 's5555555-5555-5555-5555-555555555555'),
('sub-0502-0000-0000-000000000002', 'CS502', 'Database Management Systems', 'theory', 4, 1, 1, 4, 's5555555-5555-5555-5555-555555555555'),
('sub-0503-0000-0000-000000000003', 'CS503', 'Web Technologies', 'theory', 3, 1, 1, 3, 's5555555-5555-5555-5555-555555555555'),
('sub-0504-0000-0000-000000000004', 'CS504', 'Operating Systems', 'theory', 4, 1, 1, 4, 's5555555-5555-5555-5555-555555555555'),
('sub-0511-0000-0000-000000000011', 'CSL51', 'Computer Networks Laboratory', 'practical', 3, 3, 1, 2, 's5555555-5555-5555-5555-555555555555'),
('sub-0512-0000-0000-000000000012', 'CSL52', 'Web Technologies Laboratory', 'practical', 3, 3, 1, 2, 's5555555-5555-5555-5555-555555555555'),
('sub-0521-0000-0000-000000000021', 'PE501', 'Cloud Computing Architecture', 'elective', 3, 1, 1, 3, 's5555555-5555-5555-5555-555555555555'),
('sub-0522-0000-0000-000000000022', 'PE502', 'Machine Learning Essentials', 'elective', 3, 1, 1, 3, 's5555555-5555-5555-5555-555555555555'),
('sub-0523-0000-0000-000000000023', 'PE503', 'Cyber Security & Forensics', 'elective', 3, 1, 1, 3, 's5555555-5555-5555-5555-555555555555')
ON CONFLICT (subject_code) DO NOTHING;

-- Map Labs to Practical Subjects
INSERT INTO public.lab_subjects (lab_id, subject_id) VALUES
('lab-0001-0000-0000-000000000001', 'sub-0511-0000-0000-000000000011'),
('lab-0002-0000-0000-000000000002', 'sub-0512-0000-0000-000000000012')
ON CONFLICT DO NOTHING;

-- 9. FACULTY (Employee IDs T101 to T108)
INSERT INTO public.faculty (id, employee_id, full_name, department_id, phone_number, email, max_weekly_hours, is_active) VALUES
('fac-1101-0000-0000-000000000101', 'T101', 'Dr. Ramesh Sharma', 1, '9845012341', 'ramesh.sharma@college.edu', 18, true),
('fac-1102-0000-0000-000000000102', 'T102', 'Prof. Sunita Rao', 1, '9845012342', 'sunita.rao@college.edu', 18, true),
('fac-1103-0000-0000-000000000103', 'T103', 'Prof. Anand Kumar', 1, '9845012343', 'anand.kumar@college.edu', 18, true),
('fac-1104-0000-0000-000000000104', 'T104', 'Prof. Priya Nair', 1, '9845012344', 'priya.nair@college.edu', 18, true),
('fac-1105-0000-0000-000000000105', 'T105', 'Prof. Vikram Hegde', 1, '9845012345', 'vikram.hegde@college.edu', 18, true),
('fac-1106-0000-0000-000000000106', 'T106', 'Prof. Deepa Patil', 1, '9845012346', 'deepa.patil@college.edu', 18, true),
('fac-1107-0000-0000-000000000107', 'T107', 'Prof. Karthik S', 1, '9845012347', 'karthik.s@college.edu', 18, true),
('fac-1108-0000-0000-000000000108', 'T108', 'Prof. Megha V', 1, '9845012348', 'megha.v@college.edu', 18, true)
ON CONFLICT (employee_id) DO NOTHING;

-- Map Faculty to Cluster 1
INSERT INTO public.cluster_faculty (cluster_id, faculty_id) VALUES
('c1111111-1111-1111-1111-111111111111', 'fac-1101-0000-0000-000000000101'),
('c1111111-1111-1111-1111-111111111111', 'fac-1102-0000-0000-000000000102'),
('c1111111-1111-1111-1111-111111111111', 'fac-1103-0000-0000-000000000103'),
('c1111111-1111-1111-1111-111111111111', 'fac-1104-0000-0000-000000000104'),
('c1111111-1111-1111-1111-111111111111', 'fac-1105-0000-0000-000000000105'),
('c1111111-1111-1111-1111-111111111111', 'fac-1106-0000-0000-000000000106'),
('c1111111-1111-1111-1111-111111111111', 'fac-1107-0000-0000-000000000107'),
('c1111111-1111-1111-1111-111111111111', 'fac-1108-0000-0000-000000000108')
ON CONFLICT DO NOTHING;

-- 10. FACULTY QUALIFICATIONS
INSERT INTO public.faculty_subjects (faculty_id, subject_id, is_qualified) VALUES
-- Dr. Ramesh Sharma: Networks & Networks Lab
('fac-1101-0000-0000-0000000101', 'sub-0501-0000-0000-000000000001', true),
('fac-1101-0000-0000-0000000101', 'sub-0511-0000-0000-000000000011', true),
-- Prof. Sunita Rao: DBMS & Machine Learning
('fac-1102-0000-0000-0000000102', 'sub-0502-0000-0000-000000000002', true),
('fac-1102-0000-0000-0000000102', 'sub-0522-0000-0000-000000000022', true),
-- Prof. Anand Kumar: Web Tech & Web Tech Lab & Cloud
('fac-1103-0000-0000-0000000103', 'sub-0503-0000-0000-000000000003', true),
('fac-1103-0000-0000-0000000103', 'sub-0512-0000-0000-000000000012', true),
('fac-1103-0000-0000-0000000103', 'sub-0521-0000-0000-000000000021', true),
-- Prof. Priya Nair: OS & Cyber Security
('fac-1104-0000-0000-0000000104', 'sub-0504-0000-0000-000000000004', true),
('fac-1104-0000-0000-0000000104', 'sub-0523-0000-0000-000000000023', true),
-- Prof. Vikram Hegde: Networks Lab & Web Tech Lab (Co-teacher qualified)
('fac-1105-0000-0000-0000000105', 'sub-0511-0000-0000-000000000011', true),
('fac-1105-0000-0000-0000000105', 'sub-0512-0000-0000-000000000012', true),
-- Prof. Deepa Patil: Web Tech Lab co-teacher
('fac-1106-0000-0000-0000000106', 'sub-0512-0000-0000-000000000012', true),
-- Prof. Karthik S: Networks Lab co-teacher
('fac-1107-0000-0000-0000000107', 'sub-0511-0000-0000-000000000011', true),
-- Prof. Megha V: Web Tech Lab co-teacher
('fac-1108-0000-0000-0000000108', 'sub-0512-0000-0000-000000000012', true)
ON CONFLICT DO NOTHING;

-- 11. LAB BATCHES (Section 5A: Batch 1 & 2; 5B: Batch 1 & 2; 5C: Batch 1 & 2)
INSERT INTO public.lab_batches (id, section_id, batch_name, student_count) VALUES
('btc-5a01-0000-0000-000000000001', 'sec-5a01-0000-0000-000000000001', 'Batch 1 (A1)', 30),
('btc-5a02-0000-0000-000000000002', 'sec-5a01-0000-0000-000000000001', 'Batch 2 (A2)', 30),
('btc-5b01-0000-0000-000000000001', 'sec-5b02-0000-0000-000000000002', 'Batch 1 (B1)', 30),
('btc-5b02-0000-0000-000000000002', 'sec-5b02-0000-0000-000000000002', 'Batch 2 (B2)', 30),
('btc-5c01-0000-0000-000000000001', 'sec-5c03-0000-0000-000000000003', 'Batch 1 (C1)', 30),
('btc-5c02-0000-0000-000000000002', 'sec-5c03-0000-0000-000000000003', 'Batch 2 (C2)', 30)
ON CONFLICT (section_id, batch_name) DO NOTHING;

-- 12. TIME SLOTS (Monday to Friday, 6 periods per day)
-- Day 1=Monday, 2=Tuesday, 3=Wednesday, 4=Thursday, 5=Friday
-- Period 1: 09:00 - 10:00
-- Period 2: 10:00 - 11:00
-- Break:    11:00 - 11:15
-- Period 3: 11:15 - 12:15
-- Period 4: 12:15 - 01:15
-- Lunch:    01:15 - 02:00
-- Period 5: 02:00 - 03:00
-- Period 6: 03:00 - 04:00

INSERT INTO public.time_slots (day_of_week, period_number, start_time, end_time, slot_type, is_schedulable) VALUES
-- Monday
(1, 1, '09:00:00', '10:00:00', 'class', true),
(1, 2, '10:00:00', '11:00:00', 'class', true),
(1, 3, '11:15:00', '12:15:00', 'class', true),
(1, 4, '12:15:00', '13:15:00', 'class', true),
(1, 5, '14:00:00', '15:00:00', 'class', true),
(1, 6, '15:00:00', '16:00:00', 'class', true),
-- Tuesday
(2, 1, '09:00:00', '10:00:00', 'class', true),
(2, 2, '10:00:00', '11:00:00', 'class', true),
(2, 3, '11:15:00', '12:15:00', 'class', true),
(2, 4, '12:15:00', '13:15:00', 'class', true),
(2, 5, '14:00:00', '15:00:00', 'class', true),
(2, 6, '15:00:00', '16:00:00', 'class', true),
-- Wednesday
(3, 1, '09:00:00', '10:00:00', 'class', true),
(3, 2, '10:00:00', '11:00:00', 'class', true),
(3, 3, '11:15:00', '12:15:00', 'class', true),
(3, 4, '12:15:00', '13:15:00', 'class', true),
(3, 5, '14:00:00', '15:00:00', 'class', true),
(3, 6, '15:00:00', '16:00:00', 'class', true),
-- Thursday
(4, 1, '09:00:00', '10:00:00', 'class', true),
(4, 2, '10:00:00', '11:00:00', 'class', true),
(4, 3, '11:15:00', '12:15:00', 'class', true),
(4, 4, '12:15:00', '13:15:00', 'class', true),
(4, 5, '14:00:00', '15:00:00', 'class', true),
(4, 6, '15:00:00', '16:00:00', 'class', true),
-- Friday
(5, 1, '09:00:00', '10:00:00', 'class', true),
(5, 2, '10:00:00', '11:00:00', 'class', true),
(5, 3, '11:15:00', '12:15:00', 'class', true),
(5, 4, '12:15:00', '13:15:00', 'class', true),
(5, 5, '14:00:00', '15:00:00', 'class', true),
(5, 6, '15:00:00', '16:00:00', 'class', true)
ON CONFLICT (day_of_week, period_number) DO NOTHING;
