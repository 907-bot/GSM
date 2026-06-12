from pydantic import BaseModel, Field
from datetime import datetime
from typing import Any, Optional
from enum import Enum


class EventType(str, Enum):
    # Agent lifecycle
    AGENT_SEARCH_STARTED = "agent.search.started"
    AGENT_PAPER_FOUND = "agent.paper.found"
    AGENT_PAPER_PROCESSED = "agent.paper.processed"
    AGENT_SEARCH_COMPLETED = "agent.search.completed"
    AGENT_SEARCH_FAILED = "agent.search.failed"

    # Paper pipeline
    PAPER_FETCHED = "paper.fetched"
    PAPER_PARSED = "paper.parsed"
    PAPER_EMBEDDED = "paper.embedded"
    PAPER_INDEXED = "paper.indexed"
    PAPER_FAILED = "paper.failed"

    # Replay / Dream
    REPLAY_STARTED = "replay.started"
    REPLAY_COMPLETED = "replay.completed"
    DREAM_STARTED = "dream.started"
    DREAM_COMPLETED = "dream.completed"

    # Contradictions
    CONTRADICTION_DETECTED = "contradiction.detected"
    CONTRADICTION_RESOLVED = "contradiction.resolved"

    # Bottlenecks
    BOTTLENECK_FOUND = "bottleneck.found"
    BOTTLENECK_UPDATED = "bottleneck.updated"

    # Hypotheses
    HYPOTHESIS_GENERATED = "hypothesis.generated"
    HYPOTHESIS_EVALUATED = "hypothesis.evaluated"

    # Graph
    GRAPH_RELATIONSHIP_CREATED = "graph.relationship.created"
    GRAPH_CONCEPT_CREATED = "graph.concept.created"
    GRAPH_CLUSTER_DETECTED = "graph.cluster.detected"
    GRAPH_MISSING_LINK_FOUND = "graph.missing.link.found"

    # System
    SYSTEM_HEALTH_CHANGED = "system.health.changed"
    SYSTEM_ERROR = "system.error"
    SYSTEM_METRICS = "system.metrics"

    # Progress / Streaming
    AGENT_SOURCE_PROGRESS = "agent.source.progress"
    AGENT_SEARCH_PROGRESS = "agent.search.progress"
    TASK_STATUS_CHANGE = "task.status.change"
    TASK_PROGRESS = "task.progress"

    # Pipeline
    PIPELINE_STAGE_UPDATE = "pipeline.stage.update"
    PIPELINE_QUEUE_DEPTH = "pipeline.queue.depth"


class Severity(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Event(BaseModel):
    type: EventType
    data: dict = Field(default_factory=dict)
    severity: Severity = Severity.INFO
    timestamp: datetime = Field(default_factory=datetime.now)
    room: str = "all"
    source: Optional[str] = None
    id: Optional[str] = None


class Notification(BaseModel):
    event_id: str
    title: str
    message: str
    severity: Severity
    type: EventType
    timestamp: datetime
    read: bool = False
    action_url: Optional[str] = None
