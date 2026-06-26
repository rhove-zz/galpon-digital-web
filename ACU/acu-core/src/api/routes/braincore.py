"""BrainCore API routes."""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from src.api.schemas import (
    BrainCoreMetricsResponse,
    BrainDecisionCreate,
    BrainDecisionResponse,
    BrainDomainDeleteResponse,
    BrainDomainExportResponse,
    BrainIngestRequest,
    BrainIngestResponse,
    BrainSearchRequest,
    BrainSearchResponse,
    BrainSourceDeleteResponse,
    BrainSourceResponse,
)

router = APIRouter(prefix="/braincore", tags=["braincore"])


@router.post(
    "/decisions",
    response_model=BrainDecisionResponse,
)
async def register_brain_decision(payload: BrainDecisionCreate, request: Request):
    """Register an architectural decision in BrainCore."""
    manager = request.app.state.braincore_provider()
    result = manager.register_decision(
        title=payload.title,
        context=payload.context,
        decision=payload.decision,
        alternatives=payload.alternatives,
        impact=payload.impact,
        domain=payload.domain,
        status=payload.status,
        tags=payload.tags,
    )
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    return result.get("data")


@router.get(
    "/decisions",
    response_model=List[BrainDecisionResponse],
)
async def list_brain_decisions(
    request: Request,
    search: str = "",
    domain: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=20, ge=1, le=100),
):
    """List architectural decisions stored in BrainCore."""
    manager = request.app.state.braincore_provider()
    result = manager.list_decisions(
        search=search,
        domain=domain,
        status=status,
        limit=limit,
    )
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    return result.get("data", [])


@router.get(
    "/sources",
    response_model=List[BrainSourceResponse],
)
async def list_brain_sources(
    request: Request,
    domain: Optional[str] = None,
    source_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=20, ge=1, le=100),
):
    """List sources indexed in BrainCore."""
    manager = request.app.state.braincore_provider()
    result = manager.list_sources(
        domain=domain,
        source_type=source_type,
        status=status,
        limit=limit,
    )
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    return result.get("data", [])


@router.get(
    "/metrics",
    response_model=BrainCoreMetricsResponse,
)
async def get_brain_metrics(request: Request):
    """Return aggregate BrainCore metrics for monitoring."""
    manager = request.app.state.braincore_provider()
    result = manager.get_metrics()
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    return result.get("data", {})


@router.get(
    "/domains/{domain}/export",
    response_model=BrainDomainExportResponse,
)
async def export_brain_domain(
    domain: str,
    request: Request,
    include_chunks: bool = True,
):
    """Export BrainCore records for a domain."""
    manager = request.app.state.braincore_provider()
    result = manager.export_domain(domain=domain, include_chunks=include_chunks)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    return result.get("data")


@router.delete(
    "/domains/{domain}",
    response_model=BrainDomainDeleteResponse,
)
async def delete_brain_domain(
    domain: str,
    request: Request,
    confirm: str = "",
    delete_decisions: bool = False,
):
    """Delete BrainCore sources for a domain after explicit confirmation."""
    normalized_domain = domain.strip()
    if not normalized_domain or confirm != normalized_domain:
        raise HTTPException(
            status_code=422,
            detail="confirm debe coincidir exactamente con el dominio",
        )
    manager = request.app.state.braincore_provider()
    result = manager.delete_domain(
        domain=normalized_domain,
        delete_decisions=delete_decisions,
    )
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    return result.get("data")


@router.delete(
    "/sources/{source_id}",
    response_model=BrainSourceDeleteResponse,
)
async def delete_brain_source(source_id: int, request: Request):
    """Delete an indexed BrainCore source and its chunks."""
    manager = request.app.state.braincore_provider()
    result = manager.delete_source(source_id=source_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error"))
    return result.get("data")


@router.post(
    "/ingest",
    response_model=BrainIngestResponse,
)
async def ingest_brain_source(payload: BrainIngestRequest, request: Request):
    """Ingest local files or directories into BrainCore."""
    manager = request.app.state.braincore_provider()
    result = manager.ingest_path(
        path=payload.path,
        source_type=payload.source_type,
        domain=payload.domain,
    )
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    return result.get("data")


@router.post(
    "/search",
    response_model=BrainSearchResponse,
)
async def search_brain_context(payload: BrainSearchRequest, request: Request):
    """Retrieve relevant context from ingested BrainCore chunks."""
    manager = request.app.state.braincore_provider()
    result = manager.search_context(
        query=payload.query,
        domain=payload.domain,
        source_type=payload.source_type,
        top_k=payload.top_k,
    )
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    return {
        "query": payload.query.strip(),
        "results": result.get("data", []),
    }
