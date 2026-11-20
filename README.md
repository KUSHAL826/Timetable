# SmartTimetable AI — Institutional Timetable Management & AI Optimization OS

A complete, production-oriented college timetable management and AI-powered automatic scheduling platform.

Built with **Pure Python Full-Stack (Zero Node.js / Zero npm)**. Runs in a single unified directory.

---

## 1. Quick Start

### Prerequisites
- Python 3.10+ (Tested on Python 3.13)
- No Node.js or npm required!

### Run the Application
Open your terminal in this directory and run:

```bash
# Using the pre-configured virtual environment:
.\venv\Scripts\python.exe run.py

# Or using uvicorn directly:
.\venv\Scripts\uvicorn.exe app.main:app --reload --port 8000
```

Now open your browser at **[http://localhost:8000](http://localhost:8000)**.

### Run Verification Tests
```bash
.\venv\Scripts\python.exe -m unittest tests/test_system.py
```

---

## 2. Authentication & User Roles

### A. Timetable Officer Account (Pre-Provisioned)
The platform is bootstrapped with **ONLY** the Timetable Officer account initially:

- **Officer ID:** `17301`
- **Initial Password:** `8296060284`
- **Role:** `timetable_officer`

Upon first login, the officer is prompted to update their temporary password to a permanent secure password.

### B. Faculty Account Creation by Officer
Faculties are created by the Timetable Officer from the **Faculty Management** module (`/faculty`):

1. Officer clicks **Add Teacher Account**.
2. Enters:
   - **Teacher ID / Employee ID** (e.g. `T101`, `T102`)
   - **Full Name** (e.g. `Dr. Ramesh Sharma`)
   - **College Department** (selected dynamically from autoincrement college departments `1, 2, 3...`)
   - **Phone Number** (e.g. `9845012341`)
   - Max Weekly Hours & Email
3. The platform automatically creates the teacher login:
   - **Username / ID:** Teacher ID (`T101`)
   - **Initial Password:** Registered Phone Number (`9845012341`)
   - **Role:** `teacher`
4. The system immediately shows the credentials to the officer to share with the teacher.

### C. Teacher Portal (Read-Only • No Edits • Dynamic Department)
When a Teacher logs in using their Teacher ID and phone number password:
- They are required to set a permanent secure password upon initial login.
- Their **Department Name & Code** are displayed dynamically (never hardcoded, whole-college scope).
- They can view their **Personal Timetable**, **Weekly Schedule**, **Assigned Sections**, and **Lab Practicals** (with co-teacher designations).
- **Strictly Read-Only (NO EDITS):** Teachers cannot edit academic structure, cannot modify schedules, and cannot generate or publish timetables.

### D. Multi-Department Handling & Autoincrement IDs
- Department IDs are strictly autoincrementing integers (`1, 2, 3...`) generated via backend sequence counter / SQL `SERIAL`.
- Department names and codes are dynamically resolved throughout the system (Teacher Dashboard, Faculty Roster, Cluster Configurations, and Section mappings).

---

## 3. Institutional Rule: Input First, Validation Second, Generation Last

The platform enforces a strict sequence:

```text
INPUT → VALIDATION → AI ANALYSIS → OR-TOOLS GENERATION → CONFLICT CHECK → REVIEW → APPROVAL → PUBLICATION
```

1. **Input Phase:**
   - Academic Structure: Departments, Academic Years, Semesters, Clusters, Sections.
   - Faculty Management: Qualifications and maximum workload.
   - Infrastructure: Classroom capacities, Laboratory workstation capacities.
   - Lab Staffing: Primary faculty, exact required co-teachers count, student batches.
   - Availability Matrix: Explicit availability per time slot (unknown availability is treated as incomplete).
2. **Validation Gate (`/validation`):**
   - Color-coded: Green (Complete), Yellow (Warning), Red (Blocking error).
   - Direct clickable links to fix incomplete data.
   - The **"Generate Timetable"** button remains locked until 0 blocking errors remain.
3. **OR-Tools CP-SAT Solver (`/generate`):**
   - Mathematical constraint satisfaction programming.
   - Returns true solver status: `OPTIMAL`, `FEASIBLE`, or `INFEASIBLE`.
4. **Schedule Viewer & Manual Editor (`/viewer`, `/editor`):**
   - Multi-view grid (Cluster, Section, Faculty, Room, Lab, Batch).
   - Manual override with instant conflict detection (highlights faculty clashes, room clashes, lab clashes).
5. **Excel Tools (`/excel-tools`):**
   - Download templates for bulk import.
   - Export generated schedules to Excel (`.xlsx`) or CSV.

---

## 4. Technology Stack (Single Folder • Zero Node.js)

- **Backend & Web Server:** Python FastAPI
- **Reactive UI:** Jinja2 + Tailwind CSS + Alpine.js + Lucide Icons + HTMX
- **Mathematical Scheduling:** Google OR-Tools CP-SAT (`ortools`)
- **AI Agent Orchestration:** LangGraph + Google Gemini 2.0 Flash (`google-genai`)
- **Database & Identity:** Supabase PostgreSQL with RLS (`supabase/migrations/`)
- **Spreadsheets & Reports:** `pandas`, `openpyxl`, `reportlab`

---

## 5. Directory Structure

```text
TIMETABLE/
├── app/
│   ├── main.py                     # FastAPI entry point & bootstrap
│   ├── config.py                   # Environment settings
│   ├── database.py                 # Supabase client bridging
│   ├── auth/                       # Security, JWT tokens, bcrypt
│   ├── api/                        # REST & Web UI controllers
│   ├── scheduling/                 # Google OR-Tools CP-SAT engine & validator
│   ├── agents/                     # LangGraph multi-agent team & Gemini client
│   ├── services/                   # Institutional Data Store
│   └── templates/                  # Reactive HTML interfaces
├── supabase/
│   ├── migrations/                 # PostgreSQL RLS schema
│   └── seed.sql                    # Institutional reference seed data
├── docs/                           # Architecture & schema documentation
├── run.py                          # 1-Click server runner
├── requirements.txt                # Python dependencies
├── .env                            # Environment secrets
└── README.md
```
