from typing import Dict, Any
from app.scheduling.diagnostics import ConflictDiagnostics

def resolve_and_diagnose(data: Dict[str, Any], solver_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Conflict Resolution Agent:
    When solver is infeasible or has conflicts, provides mathematical root-cause diagnosis.
    """
    diagnostics = ConflictDiagnostics.diagnose_infeasibility(data)
    return {
        "agent": "Conflict Resolution Agent",
        "diagnostics": diagnostics,
        "solver_status": solver_result.get("solver_status")
    }
