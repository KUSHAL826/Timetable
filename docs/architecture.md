# SmartTimetable AI — Architecture & Technical Design

## 1. System Overview

**SmartTimetable AI** is an institutional-grade college timetable management and automatic generation platform. It enforces strict data validation before scheduling, utilizes Google OR-Tools CP-SAT for multi-constraint optimization, and coordinates AI agents via Google Gemini and LangGraph for intelligence, conflict diagnosis, and administrative recommendations.

```
       +-------------------------------------------------------+
       |                  React + Vite Frontend                |
       |  (Tailwind CSS, Shadcn UI, TanStack Query, Zod)       |
       +---------------------------+---------------------------+
                                   | REST API / Auth
                                   v
       +-------------------------------------------------------+
       |                  FastAPI Backend Server               |
       |       Auth, Validation Engine, Diagnostic APIs        |
       +-------------+-----------------------------+-----------+
                     |                             |
       +-------------v-------------+ +-------------v-----------+
       |      OR-Tools CP-SAT      | |    LangGraph AI Agents  |
       |    Mathematical Solver    | | (Gemini 2.0 Flash Core) |
       +-------------+-------------+ +-------------+-----------+
                     |                             |
                     +-------------+---------------+
                                   |
                                   v
       +-------------------------------------------------------+
       |              Supabase PostgreSQL Database             |
       |             RLS, Storage, Auth Identity               |
       +-------------------------------------------------------+
```

## 2. Core Pillars

### A. Strict Data Pipeline: Input -> Validation -> AI Analysis -> Generation
- **Input First**: All academic structure, sections, faculty qualifications, room capacities, lab requirements, and availability matrices must be populated.
- **Validation Second**: The validation dashboard tracks blocking errors, warnings, and completed modules. Timetable generation is strictly disabled until 0 blocking errors remain.
- **OR-Tools Generation**: True constraint programming via `ortools.sat.python.cp_model`. No generative hallucinations or invented assignments.
- **AI Analysis**: LangChain and LangGraph multi-agent architecture inspects feasibility, explains bottlenecks, and suggests constraint adjustments.

### B. Dual-Role Authentication Architecture
- **Timetable Officer**: Full administrative authority over academic structures, allocations, solver runs, manual overrides, and publications.
- **Teacher**: Restricted portal viewing personal schedules, assigned lab sessions, co-teacher rosters, and notifications.

### C. Cluster-Wise Scheduling
Timetables are scheduled per cluster (e.g., Sections 5A, 5B, 5C) to resolve:
- Shared lab facilities (Networks Lab, Web Lab).
- Co-teacher allocations across practical sessions.
- Synchronized professional elective blocks.
- Shared faculty across sections.
