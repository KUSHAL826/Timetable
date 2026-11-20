from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional
from app.auth.dependencies import require_officer
from app.api.scheduling_routes import _build_cluster_data
from app.agents.orchestrator import TimetableAgentOrchestrator
from app.services.data_store import store

router = APIRouter(prefix="/ai", tags=["AI Agent Orchestration & Gemini Advisory"])

@router.post("/pre-audit")
async def run_pre_audit(cluster_id: str, user: dict = Depends(require_officer)):
    """
    Invokes the Multi-Agent audit team:
    1. Academic Planning Agent
    2. Faculty Management Agent
    3. Laboratory Management Agent
    4. Professional Elective Agent
    """
    cluster_data = _build_cluster_data(cluster_id)
    orchestrator = TimetableAgentOrchestrator()
    analysis = orchestrator.run_pre_generation_analysis(cluster_data)
    return analysis

@router.post("/advisory")
async def get_gemini_advisory(cluster_id: str, user: dict = Depends(require_officer)):
    """
    Invokes Google Gemini 2.0 Flash for senior institutional scheduling advisory.
    Provides strategic bottleneck breakdown and non-violating recommendations.
    """
    cluster_data = _build_cluster_data(cluster_id)
    orchestrator = TimetableAgentOrchestrator()
    pre_analysis = orchestrator.run_pre_generation_analysis(cluster_data)

    advisory_summary = await orchestrator.generate_gemini_advisory({
        "cluster_name": cluster_data["cluster"]["name"],
        "sections_count": len(cluster_data["sections"]),
        "faculty_count": len(cluster_data["faculty"]),
        "classrooms_count": len(cluster_data["classrooms"]),
        "laboratories_count": len(cluster_data["laboratories"]),
        "pre_analysis_findings": pre_analysis.get("findings", [])
    })

    return {
        "status": "success",
        "advisory": advisory_summary,
        "pre_analysis": pre_analysis
    }
