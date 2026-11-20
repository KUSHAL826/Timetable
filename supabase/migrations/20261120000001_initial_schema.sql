-- SMARTTIMETABLE AI: CORE SUPABASE MIGRATION
-- Migration: 20261120000001_initial_schema.sql
-- Enables UUID generation and crypto functions
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 1. USER PROFILES
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    employee_id TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('timetable_officer', 'teacher')),
    phone_number TEXT,
    must_change_password BOOLEAN NOT NULL DEFAULT true,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_profiles_role ON public.profiles(role);
CREATE INDEX IF NOT EXISTS idx_profiles_employee_id ON public.profiles(employee_id);

-- 2. DEPARTMENTS (Autoincrementing ID)
CREATE TABLE IF NOT EXISTS public.departments (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    code TEXT UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. ACADEMIC YEARS AND SEMESTERS
CREATE TABLE IF NOT EXISTS public.academic_years (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    start_date DATE,
    end_date DATE,
    is_active BOOLEAN DEFAULT false
);

CREATE TABLE IF NOT EXISTS public.semesters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    semester_number INT NOT NULL,
    academic_year_id UUID REFERENCES public.academic_years(id) ON DELETE CASCADE,
    start_date DATE,
    end_date DATE,
    UNIQUE (semester_number, academic_year_id)
);

-- 4. CLUSTERS
CREATE TABLE IF NOT EXISTS public.clusters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    department_id INT REFERENCES public.departments(id) ON DELETE SET NULL,
    semester_id UUID REFERENCES public.semesters(id) ON DELETE CASCADE,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. SECTIONS
CREATE TABLE IF NOT EXISTS public.sections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    department_id INT REFERENCES public.departments(id) ON DELETE SET NULL,
    semester_id UUID REFERENCES public.semesters(id) ON DELETE CASCADE,
    student_strength INT NOT NULL CHECK (student_strength > 0),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.cluster_sections (
    cluster_id UUID REFERENCES public.clusters(id) ON DELETE CASCADE,
    section_id UUID REFERENCES public.sections(id) ON DELETE CASCADE,
    PRIMARY KEY (cluster_id, section_id),
    UNIQUE (section_id)
);

-- 6. TEACHERS / FACULTY
CREATE TABLE IF NOT EXISTS public.faculty (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    department_id INT REFERENCES public.departments(id) ON DELETE SET NULL,
    phone_number TEXT,
    email TEXT,
    max_weekly_hours INT DEFAULT 20,
    preferred_periods JSONB DEFAULT '[]'::jsonb,
    unavailable_periods JSONB DEFAULT '[]'::jsonb,
    fixed_commitments TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.cluster_faculty (
    cluster_id UUID REFERENCES public.clusters(id) ON DELETE CASCADE,
    faculty_id UUID REFERENCES public.faculty(id) ON DELETE CASCADE,
    PRIMARY KEY (cluster_id, faculty_id)
);

-- 7. SUBJECTS
CREATE TABLE IF NOT EXISTS public.subjects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_code TEXT NOT NULL UNIQUE,
    subject_name TEXT NOT NULL,
    subject_type TEXT NOT NULL CHECK (subject_type IN ('theory', 'practical', 'elective')),
    weekly_hours INT NOT NULL DEFAULT 0,
    consecutive_periods INT DEFAULT 1,
    department_id UUID REFERENCES public.departments(id) ON DELETE SET NULL,
    credits INT DEFAULT 3,
    semester_id UUID REFERENCES public.semesters(id) ON DELETE SET NULL,
    is_active BOOLEAN DEFAULT true
);

-- 8. SUBJECT-FACULTY QUALIFICATIONS
CREATE TABLE IF NOT EXISTS public.faculty_subjects (
    faculty_id UUID REFERENCES public.faculty(id) ON DELETE CASCADE,
    subject_id UUID REFERENCES public.subjects(id) ON DELETE CASCADE,
    is_qualified BOOLEAN DEFAULT true,
    is_exception BOOLEAN DEFAULT false,
    exception_reason TEXT,
    PRIMARY KEY (faculty_id, subject_id)
);

-- 9. SECTION SUBJECT REQUIREMENTS AND FACULTY ALLOCATIONS
CREATE TABLE IF NOT EXISTS public.section_subjects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    section_id UUID REFERENCES public.sections(id) ON DELETE CASCADE,
    subject_id UUID REFERENCES public.subjects(id) ON DELETE CASCADE,
    weekly_hours INT NOT NULL,
    UNIQUE (section_id, subject_id)
);

CREATE TABLE IF NOT EXISTS public.subject_allocations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    section_subject_id UUID REFERENCES public.section_subjects(id) ON DELETE CASCADE,
    faculty_id UUID REFERENCES public.faculty(id) ON DELETE CASCADE,
    allocation_type TEXT NOT NULL DEFAULT 'primary' CHECK (allocation_type IN ('primary', 'co_teacher')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 10. TIME STRUCTURE
CREATE TABLE IF NOT EXISTS public.time_slots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    day_of_week INT NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),
    period_number INT NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    slot_type TEXT NOT NULL DEFAULT 'class' CHECK (slot_type IN ('class', 'break', 'lunch', 'fixed_activity')),
    is_schedulable BOOLEAN DEFAULT true,
    UNIQUE (day_of_week, period_number)
);

-- 11. CLASSROOMS
CREATE TABLE IF NOT EXISTS public.classrooms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_code TEXT NOT NULL UNIQUE,
    room_name TEXT,
    capacity INT NOT NULL CHECK (capacity > 0),
    room_type TEXT DEFAULT 'classroom',
    is_active BOOLEAN DEFAULT true
);

-- 12. LABORATORIES
CREATE TABLE IF NOT EXISTS public.laboratories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lab_code TEXT NOT NULL UNIQUE,
    lab_name TEXT NOT NULL,
    lab_type TEXT,
    student_capacity INT NOT NULL CHECK (student_capacity > 0),
    workstation_capacity INT,
    equipment_details TEXT,
    is_active BOOLEAN DEFAULT true
);

CREATE TABLE IF NOT EXISTS public.lab_subjects (
    lab_id UUID REFERENCES public.laboratories(id) ON DELETE CASCADE,
    subject_id UUID REFERENCES public.subjects(id) ON DELETE CASCADE,
    PRIMARY KEY (lab_id, subject_id)
);

-- 13. LAB STAFFING REQUIREMENTS
CREATE TABLE IF NOT EXISTS public.lab_staffing_requirements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    section_id UUID REFERENCES public.sections(id) ON DELETE CASCADE,
    subject_id UUID REFERENCES public.subjects(id) ON DELETE CASCADE,
    lab_id UUID REFERENCES public.laboratories(id) ON DELETE CASCADE,
    primary_faculty_id UUID REFERENCES public.faculty(id) ON DELETE CASCADE,
    required_co_teacher_count INT NOT NULL DEFAULT 0 CHECK (required_co_teacher_count >= 0),
    weekly_hours INT NOT NULL,
    consecutive_periods INT NOT NULL DEFAULT 2,
    students_per_batch INT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.lab_co_teachers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    staffing_requirement_id UUID REFERENCES public.lab_staffing_requirements(id) ON DELETE CASCADE,
    faculty_id UUID REFERENCES public.faculty(id) ON DELETE CASCADE,
    UNIQUE (staffing_requirement_id, faculty_id)
);

-- 14. LAB BATCHES
CREATE TABLE IF NOT EXISTS public.lab_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    section_id UUID REFERENCES public.sections(id) ON DELETE CASCADE,
    batch_name TEXT NOT NULL,
    student_count INT NOT NULL CHECK (student_count > 0),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (section_id, batch_name)
);

-- 15. ELECTIVES
CREATE TABLE IF NOT EXISTS public.elective_groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    semester_id UUID REFERENCES public.semesters(id) ON DELETE CASCADE,
    group_name TEXT NOT NULL,
    is_active BOOLEAN DEFAULT true
);

CREATE TABLE IF NOT EXISTS public.elective_options (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    elective_group_id UUID REFERENCES public.elective_groups(id) ON DELETE CASCADE,
    subject_id UUID REFERENCES public.subjects(id) ON DELETE CASCADE,
    faculty_id UUID REFERENCES public.faculty(id) ON DELETE SET NULL,
    classroom_id UUID REFERENCES public.classrooms(id) ON DELETE SET NULL,
    max_students INT,
    UNIQUE (elective_group_id, subject_id)
);

CREATE TABLE IF NOT EXISTS public.student_elective_counts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    elective_option_id UUID REFERENCES public.elective_options(id) ON DELETE CASCADE,
    source_section_id UUID REFERENCES public.sections(id) ON DELETE CASCADE,
    student_count INT NOT NULL CHECK (student_count >= 0),
    UNIQUE (elective_option_id, source_section_id)
);

-- 16. AVAILABILITY
CREATE TABLE IF NOT EXISTS public.faculty_availability (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    faculty_id UUID REFERENCES public.faculty(id) ON DELETE CASCADE,
    time_slot_id UUID REFERENCES public.time_slots(id) ON DELETE CASCADE,
    is_available BOOLEAN NOT NULL,
    UNIQUE (faculty_id, time_slot_id)
);

CREATE TABLE IF NOT EXISTS public.section_availability (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    section_id UUID REFERENCES public.sections(id) ON DELETE CASCADE,
    time_slot_id UUID REFERENCES public.time_slots(id) ON DELETE CASCADE,
    is_available BOOLEAN NOT NULL,
    UNIQUE (section_id, time_slot_id)
);

CREATE TABLE IF NOT EXISTS public.classroom_availability (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    classroom_id UUID REFERENCES public.classrooms(id) ON DELETE CASCADE,
    time_slot_id UUID REFERENCES public.time_slots(id) ON DELETE CASCADE,
    is_available BOOLEAN NOT NULL,
    UNIQUE (classroom_id, time_slot_id)
);

CREATE TABLE IF NOT EXISTS public.lab_availability (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lab_id UUID REFERENCES public.laboratories(id) ON DELETE CASCADE,
    time_slot_id UUID REFERENCES public.time_slots(id) ON DELETE CASCADE,
    is_available BOOLEAN NOT NULL,
    UNIQUE (lab_id, time_slot_id)
);

-- 17. TIMETABLE GENERATION AND VERSIONING
CREATE TABLE IF NOT EXISTS public.timetable_generations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cluster_id UUID REFERENCES public.clusters(id) ON DELETE SET NULL,
    semester_id UUID REFERENCES public.semesters(id) ON DELETE SET NULL,
    generated_by UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    solver_status TEXT,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft', 'generated', 'validated', 'submitted',
        'approved', 'published', 'archived', 'failed'
    )),
    input_snapshot JSONB,
    diagnostics JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.timetable_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    generation_id UUID REFERENCES public.timetable_generations(id) ON DELETE CASCADE,
    section_id UUID REFERENCES public.sections(id) ON DELETE CASCADE,
    subject_id UUID REFERENCES public.subjects(id) ON DELETE CASCADE,
    faculty_id UUID REFERENCES public.faculty(id) ON DELETE SET NULL,
    classroom_id UUID REFERENCES public.classrooms(id) ON DELETE SET NULL,
    laboratory_id UUID REFERENCES public.laboratories(id) ON DELETE SET NULL,
    lab_batch_id UUID REFERENCES public.lab_batches(id) ON DELETE SET NULL,
    time_slot_id UUID REFERENCES public.time_slots(id) ON DELETE CASCADE,
    entry_type TEXT DEFAULT 'regular' CHECK (entry_type IN ('regular', 'lab', 'elective', 'fixed')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_entries_generation ON public.timetable_entries(generation_id);
CREATE INDEX IF NOT EXISTS idx_entries_slot ON public.timetable_entries(time_slot_id);
CREATE INDEX IF NOT EXISTS idx_entries_faculty ON public.timetable_entries(faculty_id);
CREATE INDEX IF NOT EXISTS idx_entries_section ON public.timetable_entries(section_id);
CREATE INDEX IF NOT EXISTS idx_entries_room ON public.timetable_entries(classroom_id);
CREATE INDEX IF NOT EXISTS idx_entries_lab ON public.timetable_entries(laboratory_id);

CREATE TABLE IF NOT EXISTS public.timetable_approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    generation_id UUID REFERENCES public.timetable_generations(id) ON DELETE CASCADE,
    submitted_by UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    approved_by UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    approval_status TEXT NOT NULL DEFAULT 'pending' CHECK (approval_status IN ('pending', 'approved', 'rejected')),
    comments TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    approved_at TIMESTAMPTZ
);

-- 18. VALIDATION AND AUDIT
CREATE TABLE IF NOT EXISTS public.generation_conflicts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    generation_id UUID REFERENCES public.timetable_generations(id) ON DELETE CASCADE,
    severity TEXT NOT NULL CHECK (severity IN ('error', 'warning', 'info')),
    conflict_type TEXT NOT NULL,
    description TEXT NOT NULL,
    related_entity_id UUID,
    details JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    entity_type TEXT,
    entity_id UUID,
    details JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 19. RESOURCE RESERVATIONS
CREATE TABLE IF NOT EXISTS public.resource_reservations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_type TEXT NOT NULL CHECK (resource_type IN ('faculty', 'classroom', 'laboratory', 'section')),
    resource_id UUID NOT NULL,
    time_slot_id UUID REFERENCES public.time_slots(id) ON DELETE CASCADE,
    purpose TEXT NOT NULL,
    reserved_by UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 20. ROW LEVEL SECURITY (RLS) POLICIES
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.departments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.academic_years ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.semesters ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.clusters ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sections ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cluster_sections ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.faculty ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cluster_faculty ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.subjects ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.faculty_subjects ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.section_subjects ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.subject_allocations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.time_slots ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.classrooms ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.laboratories ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.lab_subjects ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.lab_staffing_requirements ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.lab_co_teachers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.lab_batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.elective_groups ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.elective_options ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.student_elective_counts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.faculty_availability ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.section_availability ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.classroom_availability ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.lab_availability ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.timetable_generations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.timetable_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.timetable_approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.generation_conflicts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.resource_reservations ENABLE ROW LEVEL SECURITY;

-- Helper function to check if current user is timetable_officer
CREATE OR REPLACE FUNCTION public.is_timetable_officer()
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM public.profiles
        WHERE id = auth.uid() AND role = 'timetable_officer' AND is_active = true
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Master data policies: Read allowed for authenticated users, Write only for timetable_officer
CREATE POLICY "Allow authenticated read on departments" ON public.departments FOR SELECT TO authenticated USING (true);
CREATE POLICY "Allow officer write on departments" ON public.departments FOR ALL TO authenticated USING (public.is_timetable_officer());

CREATE POLICY "Allow authenticated read on academic_years" ON public.academic_years FOR SELECT TO authenticated USING (true);
CREATE POLICY "Allow officer write on academic_years" ON public.academic_years FOR ALL TO authenticated USING (public.is_timetable_officer());

CREATE POLICY "Allow authenticated read on semesters" ON public.semesters FOR SELECT TO authenticated USING (true);
CREATE POLICY "Allow officer write on semesters" ON public.semesters FOR ALL TO authenticated USING (public.is_timetable_officer());

CREATE POLICY "Allow authenticated read on clusters" ON public.clusters FOR SELECT TO authenticated USING (true);
CREATE POLICY "Allow officer write on clusters" ON public.clusters FOR ALL TO authenticated USING (public.is_timetable_officer());

CREATE POLICY "Allow authenticated read on sections" ON public.sections FOR SELECT TO authenticated USING (true);
CREATE POLICY "Allow officer write on sections" ON public.sections FOR ALL TO authenticated USING (public.is_timetable_officer());

CREATE POLICY "Allow authenticated read on cluster_sections" ON public.cluster_sections FOR SELECT TO authenticated USING (true);
CREATE POLICY "Allow officer write on cluster_sections" ON public.cluster_sections FOR ALL TO authenticated USING (public.is_timetable_officer());

CREATE POLICY "Allow authenticated read on faculty" ON public.faculty FOR SELECT TO authenticated USING (true);
CREATE POLICY "Allow officer write on faculty" ON public.faculty FOR ALL TO authenticated USING (public.is_timetable_officer());

CREATE POLICY "Allow authenticated read on subjects" ON public.subjects FOR SELECT TO authenticated USING (true);
CREATE POLICY "Allow officer write on subjects" ON public.subjects FOR ALL TO authenticated USING (public.is_timetable_officer());

CREATE POLICY "Allow authenticated read on time_slots" ON public.time_slots FOR SELECT TO authenticated USING (true);
CREATE POLICY "Allow officer write on time_slots" ON public.time_slots FOR ALL TO authenticated USING (public.is_timetable_officer());

CREATE POLICY "Allow authenticated read on classrooms" ON public.classrooms FOR SELECT TO authenticated USING (true);
CREATE POLICY "Allow officer write on classrooms" ON public.classrooms FOR ALL TO authenticated USING (public.is_timetable_officer());

CREATE POLICY "Allow authenticated read on laboratories" ON public.laboratories FOR SELECT TO authenticated USING (true);
CREATE POLICY "Allow officer write on laboratories" ON public.laboratories FOR ALL TO authenticated USING (public.is_timetable_officer());

-- Timetable entries: Teachers read only published entries or their own entries; Officers read/write all
CREATE POLICY "Allow officer all on timetable_generations" ON public.timetable_generations FOR ALL TO authenticated USING (public.is_timetable_officer());
CREATE POLICY "Allow teacher read published generations" ON public.timetable_generations FOR SELECT TO authenticated USING (status = 'published');

CREATE POLICY "Allow officer all on timetable_entries" ON public.timetable_entries FOR ALL TO authenticated USING (public.is_timetable_officer());
CREATE POLICY "Allow teacher read published timetable_entries" ON public.timetable_entries FOR SELECT TO authenticated USING (
    EXISTS (
        SELECT 1 FROM public.timetable_generations tg
        WHERE tg.id = timetable_entries.generation_id AND tg.status = 'published'
    )
);

-- Profiles policy: Users can read their own profile, officer can read all
CREATE POLICY "Users read own profile" ON public.profiles FOR SELECT TO authenticated USING (id = auth.uid() OR public.is_timetable_officer());
CREATE POLICY "Officer manage profiles" ON public.profiles FOR ALL TO authenticated USING (public.is_timetable_officer());
