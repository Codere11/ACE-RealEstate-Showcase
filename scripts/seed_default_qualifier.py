from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.db import session_scope
from app.models.orm import Organization, Qualifier


def main() -> int:
    org_slug = sys.argv[1] if len(sys.argv) > 1 else None
    if not org_slug:
        print("Usage: python scripts/seed_default_qualifier.py <org-slug>")
        return 1

    with session_scope() as db:
        org = db.query(Organization).filter(Organization.slug == org_slug).first()
        if not org:
            print(f"Organization not found: {org_slug}")
            return 2

        existing_live = db.query(Qualifier).filter(
            Qualifier.organization_id == org.id,
            Qualifier.status == "live",
        ).first()
        if existing_live:
            print(f"Live qualifier already exists: {existing_live.slug}")
            return 0

        existing = db.query(Qualifier).filter(
            Qualifier.organization_id == org.id,
            Qualifier.slug == "default-ai-qualifier",
        ).first()
        if existing:
            existing.status = "live"
            existing.published_at = existing.published_at or datetime.utcnow()
            print(f"Promoted existing qualifier to live: {existing.slug}")
            return 0

        q = Qualifier(
            organization_id=org.id,
            name="Default AI Qualifier",
            slug="default-ai-qualifier",
            status="live",
            system_prompt=(
                "You are ACE's qualification assistant. Be concise, useful, and non-pushy. "
                "Understand the visitor, extract only grounded facts, and avoid asking too many questions."
            ),
            assistant_style="friendly, concise, consultative",
            goal_definition="Understand visitor intent, qualify lead quality, and decide whether human takeover should be offered.",
            field_schema={
                "intent": {"type": "string", "required": False},
                "urgency": {"type": "string", "required": False},
                "timeline": {"type": "string", "required": False},
                "budget": {"type": "string", "required": False},
                "location": {"type": "string", "required": False},
                "contact_name": {"type": "string", "required": False},
                "contact_email": {"type": "string", "required": False},
                "contact_phone": {"type": "string", "required": False},
                "human_request": {"type": "boolean", "required": False},
                "objections": {"type": "array", "required": False}
            },
            required_fields=["intent"],
            scoring_rules={"notes": "Runtime heuristic + LLM extraction assisted scoring"},
            band_thresholds={"hot_min": 80, "warm_min": 50, "cold_max": 49},
            confidence_thresholds={"overall_min_for_takeover": 0.7, "field_min_for_fact_persistence": 0.6},
            takeover_rules={
                "offer_on_explicit_human_request": True,
                "offer_on_hot_band": True,
                "offer_on_video_eligible": True,
            },
            video_offer_rules={
                "enabled": True,
                "requires_takeover_eligible": True,
                "operator_can_offer_manually": True,
            },
            rag_enabled=False,
            knowledge_source_ids=[],
            max_clarifying_questions=3,
            contact_capture_policy="when_high_intent_or_explicit",
            version=1,
            version_notes="Seeded default qualifier",
            published_at=datetime.utcnow(),
        )
        db.add(q)
        print(f"Created live qualifier for org {org.slug}: {q.slug}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
