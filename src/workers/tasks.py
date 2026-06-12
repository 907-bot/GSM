import asyncio
import uuid
from functools import wraps
from .celery_app import celery_app
from ..agents import (
    BiologyAgent,
    AIAgent,
    MaterialsAgent,
    MedicineAgent,
    ChemistryAgent,
    PhysicsAgent,
)
from ..engines import (
    ReplayEngine,
    ContradictionEngine,
    BottleneckEngine,
    HypothesisGenerator,
)
from ..bus import event_bus
from ..events import Event, EventType, Severity
import structlog

logger = structlog.get_logger()


def emit_task_progress(task_name: str):
    """Decorator that wraps a Celery task to emit TASK_STATUS_CHANGE events."""
    def decorator(task_fn):
        @wraps(task_fn)
        def wrapper(self, *args, **kwargs):
            task_id = str(uuid.uuid4())
            asyncio.run(event_bus.publish(Event(
                type=EventType.TASK_STATUS_CHANGE,
                data={
                    "task_id": task_id,
                    "task_name": task_name,
                    "status": "started",
                    "args": str(args)[:100],
                    "kwargs": str({k: v for k, v in kwargs.items() if k != "self"})[:100],
                },
                room="pipeline",
                source="celery",
            )))
            try:
                result = task_fn(self, *args, **kwargs)
                asyncio.run(event_bus.publish(Event(
                    type=EventType.TASK_STATUS_CHANGE,
                    data={"task_id": task_id, "task_name": task_name, "status": "completed"},
                    room="pipeline",
                    source="celery",
                )))
                return result
            except Exception as e:
                asyncio.run(event_bus.publish(Event(
                    type=EventType.TASK_STATUS_CHANGE,
                    data={"task_id": task_id, "task_name": task_name, "status": "failed", "error": str(e)},
                    room="pipeline",
                    severity=Severity.CRITICAL,
                    source="celery",
                )))
                raise
        return wrapper
    return decorator


@celery_app.task(bind=True, name="src.workers.tasks.search_biology")
@emit_task_progress("search_biology")
def search_biology(self):
    """Search for biology papers."""
    agent = BiologyAgent()
    result = asyncio.run(agent.run_search_cycle())
    logger.info("Biology search completed", result=result)
    return result


@celery_app.task(bind=True, name="src.workers.tasks.search_ai")
@emit_task_progress("search_ai")
def search_ai(self):
    """Search for AI papers."""
    agent = AIAgent()
    result = asyncio.run(agent.run_search_cycle())
    logger.info("AI search completed", result=result)
    return result


@celery_app.task(bind=True, name="src.workers.tasks.search_materials")
@emit_task_progress("search_materials")
def search_materials(self):
    """Search for materials science papers."""
    agent = MaterialsAgent()
    result = asyncio.run(agent.run_search_cycle())
    logger.info("Materials search completed", result=result)
    return result


@celery_app.task(bind=True, name="src.workers.tasks.search_medicine")
@emit_task_progress("search_medicine")
def search_medicine(self):
    """Search for medicine papers."""
    agent = MedicineAgent()
    result = asyncio.run(agent.run_search_cycle())
    logger.info("Medicine search completed", result=result)
    return result


@celery_app.task(bind=True, name="src.workers.tasks.search_chemistry")
@emit_task_progress("search_chemistry")
def search_chemistry(self):
    """Search for chemistry papers."""
    agent = ChemistryAgent()
    result = asyncio.run(agent.run_search_cycle())
    logger.info("Chemistry search completed", result=result)
    return result


@celery_app.task(bind=True, name="src.workers.tasks.search_physics")
@emit_task_progress("search_physics")
def search_physics(self):
    """Search for physics papers."""
    agent = PhysicsAgent()
    result = asyncio.run(agent.run_search_cycle())
    logger.info("Physics search completed", result=result)
    return result


@celery_app.task(bind=True, name="src.workers.tasks.run_replay")
@emit_task_progress("run_replay")
def run_replay(self):
    """Run the scientific replay system."""
    engine = ReplayEngine()
    result = asyncio.run(engine.replay_memories())
    logger.info("Replay completed", result=result)
    return result


@celery_app.task(bind=True, name="src.workers.tasks.detect_contradictions")
@emit_task_progress("detect_contradictions")
def detect_contradictions(self):
    """Detect contradictions in recent findings."""
    engine = ContradictionEngine()
    summary = asyncio.run(engine.get_contradiction_summary())
    logger.info("Contradiction detection completed", summary=summary)
    return summary


@celery_app.task(bind=True, name="src.workers.tasks.detect_bottlenecks")
@emit_task_progress("detect_bottlenecks")
def detect_bottlenecks(self):
    """Detect bottlenecks across fields."""
    engine = BottleneckEngine()
    fields = ["biology", "ai", "medicine", "materials", "chemistry", "physics"]

    results = []
    for i, field in enumerate(fields):
        result = asyncio.run(engine.detect_bottlenecks(field))
        results.append({"field": field, "bottlenecks": len(result)})
        asyncio.run(event_bus.publish(Event(
            type=EventType.TASK_PROGRESS,
            data={
                "task_name": "detect_bottlenecks",
                "field": field,
                "progress": f"{i + 1}/{len(fields)}",
                "bottlenecks_found": len(result),
            },
            room="pipeline",
            source="celery",
        )))

    logger.info("Bottleneck detection completed", results=results)
    return results


@celery_app.task(bind=True, name="src.workers.tasks.generate_hypotheses")
@emit_task_progress("generate_hypotheses")
def generate_hypotheses(self):
    """Generate new hypotheses."""
    generator = HypothesisGenerator()
    hypotheses = asyncio.run(generator.generate_hypotheses(num_hypotheses=10))
    logger.info("Hypothesis generation completed", count=len(hypotheses))
    return {"hypotheses_generated": len(hypotheses)}


@celery_app.task(bind=True, name="src.workers.tasks.run_dream_cycle")
@emit_task_progress("run_dream_cycle")
def run_dream_cycle(self):
    """Run the digital dreaming cycle."""
    engine = ReplayEngine()
    result = asyncio.run(engine.dream(duration_minutes=60))
    logger.info("Dream cycle completed", result=result)
    return result


@celery_app.task(bind=True, name="src.workers.tasks.process_paper")
@emit_task_progress("process_paper")
def process_paper(self, paper_data: dict):
    """Process a single paper."""
    from ..agents.research_agent import BaseResearchAgent

    agent = BaseResearchAgent(domain="general", keywords=[])
    paper = asyncio.run(agent.process_paper(paper_data))

    if paper:
        return {"status": "success", "paper_id": str(paper.id)}
    return {"status": "failed"}
