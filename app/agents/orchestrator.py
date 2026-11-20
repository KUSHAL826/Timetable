import json
import logging
from typing import Dict, Any, List
from app.config import settings
from app.agents.academic_agent import analyze_academic_structure
from app.agents.faculty_agent import analyze_faculty_assignments
from app.agents.laboratory_agent import analyze_laboratory_staffing
from app.agents.elective_agent import analyze_electives_structure
from app.agents.optimization_agent import execute_optimization
from app.agents.conflict_agent import resolve_and_diagnose

logger = logging.getLogger(__name__)

class TimetableAgentOrchestrator:
    """
    LangGraph-compatible Multi-Agent Orchestrator.
    Coordinates Academic, Faculty, Lab, Elective, Optimization, and Conflict agents.
    Uses Google Gemini for intelligent executive summary & recommendations.
    """

    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.model_name = settings.GEMINI_MODEL

    def run_pre_generation_analysis(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Runs the four specialized domain audit agents."""
        academic_res = analyze_academic_structure(data)
        faculty_res = analyze_faculty_assignments(data)
        lab_res = analyze_laboratory_staffing(data)
        elective_res = analyze_electives_structure(data)

        all_findings = (
            academic_res.get("findings", []) +
            faculty_res.get("findings", []) +
            lab_res.get("findings", []) +
            elective_res.get("findings", [])
        )

        has_blocking_errors = any(f.get("level") == "error" for f in all_findings)

        return {
            "can_generate": not has_blocking_errors,
            "has_blocking_errors": has_blocking_errors,
            "academic": academic_res,
            "faculty": faculty_res,
            "laboratory": lab_res,
            "electives": elective_res,
            "total_findings": len(all_findings),
            "findings": all_findings
        }

    def generate_and_optimize(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validates inputs, optimizes via OR-Tools, and diagnoses any bottlenecks."""
        pre_check = self.run_pre_generation_analysis(data)
        if pre_check["has_blocking_errors"]:
            return {
                "success": False,
                "status": "VALIDATION_FAILED",
                "message": "Timetable generation blocked by validation errors. Resolve all blocking issues first.",
                "analysis": pre_check
            }

        # Invoke OR-Tools optimization agent
        opt_res = execute_optimization(data)
        solver_res = opt_res.get("result", {})

        if solver_res.get("solver_status") in ("OPTIMAL", "FEASIBLE"):
            return {
                "success": True,
                "status": "GENERATED",
                "solver_status": solver_res.get("solver_status"),
                "solve_time_seconds": solver_res.get("solve_time_seconds"),
                "entries_count": solver_res.get("entries_count"),
                "entries": solver_res.get("entries"),
                "analysis": pre_check
            }
        else:
            conflict_diag = resolve_and_diagnose(data, solver_res)
            return {
                "success": False,
                "status": "INFEASIBLE",
                "solver_status": solver_res.get("solver_status"),
                "solve_time_seconds": solver_res.get("solve_time_seconds"),
                "message": "No valid schedule exists for the current constraints.",
                "diagnostics": conflict_diag,
                "analysis": pre_check
            }

    async def generate_gemini_advisory(self, context: Dict[str, Any]) -> str:
        """Invokes Google Gemini model to deliver administrative insight."""
        if not self.api_key or "YOUR_GEMINI" in self.api_key:
            return "Gemini API key not configured. Agent analysis performed via internal deterministic logic."

        try:
            from google import genai
            client = genai.Client(api_key=self.api_key)
            prompt = (
                "You are SmartTimetable AI Senior Institutional Scheduling Consultant.\n"
                "Analyze the following institutional timetable validation and solver context:\n"
                f"{json.dumps(context, default=str)}\n\n"
                "Provide an executive, concise summary for the Timetable Officer highlighting:\n"
                "1. Schedulability and feasibility status\n"
                "2. Specific resource bottlenecks or lab staffing gaps\n"
                "3. Pragmatic recommendations without relaxing hard institutional limits."
            )
            response = client.models.generate_content(
                model=self.model_name,
                contents=prompt,
            )
            return response.text or "Analysis generated successfully."
        except Exception as e:
            logger.warning(f"Gemini advisory call failed: {e}")
            return f"Agent analysis completed. Advisory note: {str(e)}"
