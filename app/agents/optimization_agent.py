from typing import Dict, Any
from app.scheduling.engine import TimetableScheduler

def execute_optimization(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Timetable Optimization Agent:
    Prepares verified mathematical scheduling problem and invokes Google OR-Tools CP-SAT.
    """
    scheduler = TimetableScheduler(data)
    result = scheduler.solve()
    return {
        "agent": "Timetable Optimization Agent",
        "result": result
    }
