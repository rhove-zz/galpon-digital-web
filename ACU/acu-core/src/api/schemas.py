"""Request and response schemas for the ACU REST API."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Payload for a chat turn."""

    message: str = Field(..., min_length=1)
    domain: str = Field(default="generic", min_length=1)
    persona: str = Field(default="default", min_length=1)
    session_id: Optional[str] = None


class ToolExecutionResponse(BaseModel):
    """Serialized tool execution returned by chat responses."""

    tool: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    execution_time_ms: float


class ChatResponse(BaseModel):
    """Structured response for a chat turn."""

    session_id: str
    response: str
    iterations: int
    tool_calls: List[ToolExecutionResponse] = Field(default_factory=list)


class BrainDecisionCreate(BaseModel):
    """Payload for a BrainCore architectural decision."""

    title: str = Field(..., min_length=1)
    context: str = Field(..., min_length=1)
    decision: str = Field(..., min_length=1)
    alternatives: List[str] = Field(default_factory=list)
    impact: str = ""
    domain: str = Field(default="generic", min_length=1)
    status: str = Field(default="accepted", min_length=1)
    tags: List[str] = Field(default_factory=list)


class BrainDecisionResponse(BaseModel):
    """BrainCore architectural decision returned by the API."""

    id: int
    title: str
    context: str
    decision: str
    alternatives: List[str] = Field(default_factory=list)
    impact: str = ""
    domain: str
    status: str
    tags: List[str] = Field(default_factory=list)
    created_at: str
    updated_at: str


class BrainIngestRequest(BaseModel):
    """Payload for BrainCore local source ingestion."""

    path: str = Field(..., min_length=1)
    source_type: str = Field(default="auto", min_length=1)
    domain: str = Field(default="generic", min_length=1)


class BrainIngestResponse(BaseModel):
    """Summary returned after BrainCore ingestion."""

    path: str
    files_found: int
    sources_indexed: int
    chunks_indexed: int
    vector_indexed: bool = False
    skipped_sources: int
    errors: List[Any] = Field(default_factory=list)


class BrainSourceResponse(BaseModel):
    """BrainCore indexed source metadata returned by the API."""

    id: int
    source_path: str
    source_type: str
    content_hash: str
    metadata: Any = Field(default_factory=dict)
    status: str
    chunks_count: int = 0
    indexed_at: str
    updated_at: str


class BrainSourceDeleteResponse(BaseModel):
    """BrainCore source deletion summary."""

    source_id: int
    source_path: str
    deleted: bool
    vector_deleted: bool = False


class BrainDomainExportResponse(BaseModel):
    """BrainCore domain export payload."""

    domain: str
    decisions_count: int = 0
    sources_count: int = 0
    chunks_count: int = 0
    decisions: List[Any] = Field(default_factory=list)
    sources: List[Any] = Field(default_factory=list)
    chunks: List[Any] = Field(default_factory=list)


class BrainDomainDeleteResponse(BaseModel):
    """BrainCore domain deletion summary."""

    domain: str
    sources_deleted: int = 0
    chunks_deleted: int = 0
    decisions_deleted: int = 0
    vector_sources_deleted: int = 0
    deleted_source_paths: List[str] = Field(default_factory=list)


class BrainCoreMetricBucket(BaseModel):
    """Aggregated BrainCore count bucket."""

    name: str
    sources_count: int = 0
    chunks_count: int = 0


class BrainCoreMetricsResponse(BaseModel):
    """BrainCore aggregate operational metrics."""

    decisions_count: int = 0
    sources_count: int = 0
    chunks_count: int = 0
    domains_count: int = 0
    last_indexed_at: Optional[str] = None
    last_updated_at: Optional[str] = None
    domains: List[BrainCoreMetricBucket] = Field(default_factory=list)
    source_types: List[BrainCoreMetricBucket] = Field(default_factory=list)


class VectorStoreStatusResponse(BaseModel):
    """Lightweight status for the configured BrainCore vector backend."""

    enabled: bool = False
    available: bool = False
    engine: str = ""
    persist_directory: str = ""
    embedding_model: str = ""
    collection_name: str = ""
    index_path: Optional[str] = None
    metadata_path: Optional[str] = None
    index_exists: bool = False
    metadata_exists: bool = False
    records_count: int = 0
    cached: bool = False
    status: str = "disabled"
    error: Optional[str] = None


class PendingToolsMetricsResponse(BaseModel):
    """Aggregate status of HITL tool approvals."""

    total: int = 0
    pending: int = 0
    approved: int = 0
    executed: int = 0
    failed: int = 0
    rejected: int = 0
    resumed: int = 0


class SchedulerMetricsResponse(BaseModel):
    """Scheduler runtime status."""

    mode: str = "disabled"
    valid_mode: bool = True
    running: bool = False
    jobs_count: int = 0
    jobs: List[str] = Field(default_factory=list)


class RedisMetricsResponse(BaseModel):
    """Redis runtime status."""

    enabled: bool = False
    connected: bool = False
    backend: str = "local"


class WebhookChannelMetricsResponse(BaseModel):
    """Webhook counters for one channel."""

    received: int = 0
    accepted: int = 0
    rejected: int = 0
    ignored: int = 0
    processed: int = 0
    failed: int = 0
    last_event_at: Optional[float] = None
    last_error: Optional[str] = None


class WebhookMetricsResponse(BaseModel):
    """Webhook operational metrics grouped by channel."""

    total: WebhookChannelMetricsResponse = Field(
        default_factory=WebhookChannelMetricsResponse
    )
    channels: Dict[str, WebhookChannelMetricsResponse] = Field(default_factory=dict)


class SystemMetricsResponse(BaseModel):
    """System-level operational metrics for monitoring."""

    service: str
    version: str
    vector_store: VectorStoreStatusResponse
    api_auth_required: bool = False
    rate_limit_enabled: bool = False
    payload_limit_enabled: bool = False
    cors_enabled: bool = False
    pending_tools: PendingToolsMetricsResponse = Field(
        default_factory=PendingToolsMetricsResponse
    )
    scheduler: SchedulerMetricsResponse = Field(
        default_factory=SchedulerMetricsResponse
    )
    redis: RedisMetricsResponse = Field(default_factory=RedisMetricsResponse)
    webhooks: WebhookMetricsResponse = Field(default_factory=WebhookMetricsResponse)


class SystemReadinessCheckResponse(BaseModel):
    """One runtime readiness check for exposed environments."""

    name: str
    status: str
    severity: str
    detail: str


class SystemReadinessSummaryResponse(BaseModel):
    """Aggregated readiness check counts."""

    passed: int = 0
    warnings: int = 0
    failed: int = 0


class SystemReadinessResponse(BaseModel):
    """Runtime readiness checklist for operational exposure."""

    service: str
    version: str
    api_version: str
    status: str
    summary: SystemReadinessSummaryResponse = Field(
        default_factory=SystemReadinessSummaryResponse
    )
    checks: List[SystemReadinessCheckResponse] = Field(default_factory=list)


class ApiVersionResponse(BaseModel):
    """Published API contract metadata."""

    service: str
    runtime_version: str
    api_version: str
    stability: str
    openapi_url: str


class BrainSearchRequest(BaseModel):
    """Payload for BrainCore context retrieval."""

    query: str = Field(..., min_length=1)
    domain: Optional[str] = None
    source_type: Optional[str] = None
    top_k: int = Field(default=5, ge=1, le=20)


class BrainSearchResult(BaseModel):
    """One BrainCore context retrieval result."""

    chunk_id: int
    source_id: int
    source_path: str
    source_type: str
    title: str
    content: str
    similarity: float
    metadata: Any = Field(default_factory=dict)
    indexed_at: str


class BrainSearchResponse(BaseModel):
    """BrainCore retrieval response."""

    query: str
    results: List[BrainSearchResult] = Field(default_factory=list)


class AgentSessionResponse(BaseModel):
    """Persisted ACU agent session."""

    session_id: str
    domain: Optional[str] = None
    started_at: str
    ended_at: Optional[str] = None
    total_iterations: Optional[int] = None
    status: Optional[str] = None


class ConversationTurnResponse(BaseModel):
    """Persisted conversation exchange."""

    id: int
    session_id: str
    user_query: str
    agent_response: str
    timestamp: str
    steps_used: Optional[int] = None


class ToolAuditResponse(BaseModel):
    """Persisted tool execution audit row."""

    id: int
    tool_name: str
    parameters: Any = None
    result: Any = None
    execution_time_ms: Optional[int] = None
    success: bool
    executed_at: str


class ApiAccessLogResponse(BaseModel):
    """Persisted API access audit row."""

    id: int
    method: str
    path: str
    status_code: int
    key_fingerprint: Optional[str] = None
    roles: List[str] = Field(default_factory=list)
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None
    authorized: bool
    duration_ms: Optional[int] = None
    accessed_at: str


class ApiKeyCreateRequest(BaseModel):
    """Payload for creating a managed API key."""

    name: str = Field(..., min_length=1)
    roles: List[str] = Field(..., min_length=1)
    expires_at: Optional[str] = None


class ApiKeyResponse(BaseModel):
    """Managed API key metadata. The raw key is only returned on creation."""

    id: int
    name: str
    key_fingerprint: str
    roles: List[str] = Field(default_factory=list)
    status: str
    created_by: Optional[str] = None
    created_at: str
    revoked_at: Optional[str] = None
    expires_at: Optional[str] = None
    last_used_at: Optional[str] = None


class ApiKeyCreateResponse(ApiKeyResponse):
    """Managed API key creation response with one-time secret."""

    api_key: str
