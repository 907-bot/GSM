"""Data retention, archival, and lifecycle management for enterprise compliance."""

import json
import os
import shutil
import asyncio
import time
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
import structlog

from ..config import settings
from ..memory.episodic import EpisodicMemory
from ..memory.provenance import SOURCE_RELIABILITY

logger = structlog.get_logger()


@dataclass
class RetentionPolicy:
    """Defines a data retention rule."""

    name: str
    max_age_days: Optional[int] = None
    min_quality_score: Optional[float] = None
    sources_to_keep: Optional[List[str]] = None
    sources_to_purge: Optional[List[str]] = None
    archive_inactive_days: Optional[int] = None
    action: str = "archive"


DEFAULT_POLICIES = {
    "default": RetentionPolicy(
        name="default",
        max_age_days=365,
        min_quality_score=0.3,
        archive_inactive_days=90,
    ),
    "low_quality": RetentionPolicy(
        name="low_quality",
        min_quality_score=0.1,
        max_age_days=30,
        action="delete",
    ),
    "unknown_source": RetentionPolicy(
        name="unknown_source",
        sources_to_purge=["unknown", "manual"],
        action="delete",
    ),
}


class RetentionService:
    """Manages paper lifecycle: archival, purging, and cold storage."""

    def __init__(self):
        self.episodic = EpisodicMemory()
        self._policies: Dict[str, RetentionPolicy] = dict(DEFAULT_POLICIES)
        self._archive_dir = Path("data/archive")
        self._archive_dir.mkdir(parents=True, exist_ok=True)
        self._cold_storage_dir = Path("data/cold_storage")
        self._cold_storage_dir.mkdir(parents=True, exist_ok=True)

    def get_policies(self) -> Dict[str, RetentionPolicy]:
        return dict(self._policies)

    def set_policy(self, name: str, policy: RetentionPolicy) -> None:
        self._policies[name] = policy
        self._save_policies()
        logger.info("Retention policy set", name=name, action=policy.action)

    def remove_policy(self, name: str) -> bool:
        if name in self._policies and name != "default":
            del self._policies[name]
            self._save_policies()
            return True
        return False

    async def apply_policies(self, dry_run: bool = False) -> Dict[str, Any]:
        """Apply all retention policies to papers in memory.

        Returns stats about what would be / was affected.
        """
        stats = {
            "scanned": 0,
            "to_archive": 0,
            "to_delete": 0,
            "errors": 0,
            "archived": 0,
            "deleted": 0,
        }

        # Get all papers
        papers, total = await self.episodic.search_papers(limit=1000)
        stats["scanned"] = total

        for paper in papers:
            try:
                paper_id = str(paper.get("id", ""))
                payload = paper.get("payload", {}) or {}
                result = self._evaluate_paper(payload)

                if result["action"] == "skip":
                    continue

                if dry_run:
                    stats[f"to_{result['action']}"] += 1
                    continue

                if result["action"] == "archive":
                    ok = await self._archive_paper(paper_id, payload)
                    if ok:
                        stats["archived"] += 1
                    else:
                        stats["errors"] += 1

                elif result["action"] == "delete":
                    ok = await self.episodic.delete_paper(paper_id)
                    if ok:
                        stats["deleted"] += 1
                        await self._cold_store_paper(paper_id, payload)
                    else:
                        stats["errors"] += 1

            except Exception as e:
                stats["errors"] += 1
                logger.error("Retention policy error", error=str(e))

        logger.info("Retention policies applied", **stats)
        return stats

    def _evaluate_paper(self, payload: Dict[str, Any]) -> Dict[str, str]:
        """Evaluate a paper against all policies. Returns {'action': 'archive'|'delete'|'skip'}."""
        published_at = payload.get("published_at", "")
        quality_score = payload.get("quality_score")
        source = payload.get("source", "unknown")
        provenance = payload.get("provenance", {}) or {}

        age_days = None
        if published_at:
            try:
                pub_date = datetime.fromisoformat(str(published_at).replace("Z", "+00:00"))
                age_days = (datetime.now(timezone.utc) - pub_date).days
            except (ValueError, TypeError):
                pass

        for policy_name, policy in self._policies.items():
            if policy.action == "delete":
                # Check source purge
                if policy.sources_to_purge and source in policy.sources_to_purge:
                    return {"action": "delete", "reason": f"source:{source}", "policy": policy_name}

                # Check age + quality for delete
                if age_days is not None and policy.max_age_days:
                    if age_days > policy.max_age_days:
                        if policy.min_quality_score is not None:
                            qs = quality_score if quality_score is not None else 0
                            if qs < policy.min_quality_score:
                                return {"action": "delete", "reason": f"old+low_quality", "policy": policy_name}

            elif policy.action == "archive":
                # Check inactive age
                if age_days is not None and policy.archive_inactive_days:
                    if age_days > policy.archive_inactive_days:
                        return {"action": "archive", "reason": f"inactive:{age_days}d", "policy": policy_name}

                # Check max age
                if age_days is not None and policy.max_age_days:
                    if age_days > policy.max_age_days:
                        return {"action": "archive", "reason": f"old:{age_days}d", "policy": policy_name}

        return {"action": "skip"}

    async def _archive_paper(self, paper_id: str, payload: Dict[str, Any]) -> bool:
        """Archive a paper: save to archive dir, then soft-delete from Qdrant."""
        try:
            archive_file = self._archive_dir / f"{paper_id}.json"
            archive_data = {
                "id": paper_id,
                "payload": payload,
                "archived_at": datetime.now(timezone.utc).isoformat(),
            }
            archive_file.write_text(json.dumps(archive_data, default=str, indent=2))

            # Mark archived in Qdrant
            await self.episodic.archive_paper(paper_id)
            logger.info("Paper archived", paper_id=paper_id, path=str(archive_file))
            return True
        except Exception as e:
            logger.error("Failed to archive paper", paper_id=paper_id, error=str(e))
            return False

    async def _cold_store_paper(self, paper_id: str, payload: Dict[str, Any]) -> bool:
        """Save deleted paper payload to cold storage before permanent deletion."""
        try:
            store_file = self._cold_storage_dir / f"{paper_id}.json"
            store_data = {
                "id": paper_id,
                "payload": payload,
                "deleted_at": datetime.now(timezone.utc).isoformat(),
            }
            store_file.write_text(json.dumps(store_data, default=str, indent=2))
            logger.info("Paper sent to cold storage", paper_id=paper_id)
            return True
        except Exception as e:
            logger.error("Failed to cold store paper", error=str(e))
            return False

    async def restore_from_archive(self, paper_id: str) -> bool:
        """Restore an archived paper back to Qdrant."""
        archive_file = self._archive_dir / f"{paper_id}.json"
        if not archive_file.exists():
            logger.warning("Archived paper not found", paper_id=paper_id)
            return False

        try:
            data = json.loads(archive_file.read_text())
            payload = data.get("payload", {})

            # Remove archived flag
            payload.pop("archived", None)
            payload.pop("archived_at", None)

            ok = await self.episodic.update_paper(paper_id, payload)
            if ok:
                archive_file.unlink()
                logger.info("Paper restored from archive", paper_id=paper_id)
            return ok
        except Exception as e:
            logger.error("Failed to restore paper", error=str(e))
            return False

    async def list_archived(self) -> List[Dict[str, Any]]:
        """List all archived papers."""
        archived = []
        for f in sorted(self._archive_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text())
                archived.append({
                    "id": data.get("id"),
                    "title": (data.get("payload", {}) or {}).get("title", "Unknown"),
                    "archived_at": data.get("archived_at"),
                })
            except Exception:
                pass
        return archived

    def _save_policies(self) -> None:
        """Persist custom policies to disk."""
        config_path = Path("configs/retention_policies.json")
        config_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = {
                name: {
                    "name": p.name,
                    "max_age_days": p.max_age_days,
                    "min_quality_score": p.min_quality_score,
                    "sources_to_keep": p.sources_to_keep,
                    "sources_to_purge": p.sources_to_purge,
                    "archive_inactive_days": p.archive_inactive_days,
                    "action": p.action,
                }
                for name, p in self._policies.items()
            }
            config_path.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error("Failed to save retention policies", error=str(e))


retention_service = RetentionService()
