#!/usr/bin/env python3
"""
Ensure demo organization + active qualifier exist in the database.
Idempotent — safe to run multiple times.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.db import SessionLocal, engine
from app.models.orm import Organization, Qualifier, User, Base
from app.auth.security import hash_password


def ensure_demo():
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        org = db.query(Organization).filter(Organization.slug == "demo").first()
        if not org:
            org = Organization(name="Demo Salon", slug="demo", active=True)
            db.add(org)
            db.commit()
            db.refresh(org)
            print(f"✅ Created org: {org.name} (id={org.id})")
        else:
            print(f"ℹ️  Org exists: {org.name} (id={org.id})")

        qual = db.query(Qualifier).filter(
            Qualifier.organization_id == org.id,
            Qualifier.status == "live",
        ).first()
        if not qual:
            qual = Qualifier(
                organization_id=org.id,
                name="AI Receptor",
                slug="ai-receptor",
                status="live",
                system_prompt="Ti si AI Receptor za kozmetični salon Lepota & Sprostitev. Si prijazen, topel, profesionalen. Govoriš naravno slovenščino z vikanjem. Pomagaš strankam pri izbiri tretmajev, odgovarjaš na vprašanja o cenah in storitvah, ter rezerviraš termine.",
                assistant_style="prijazen, topel, profesionalen, kratek",
                goal_definition="Pomagaj obiskovalcem kozmetičnega salona pri izbiri storitev, odgovori na vprašanja, rezerviraj termine, predlagaj dopolnitve.",
                max_clarifying_questions=3,
                contact_capture_policy="when_high_intent_or_explicit",
                version=1,
            )
            db.add(qual)
            db.commit()
            print(f"✅ Created qualifier: {qual.name} (id={qual.id})")
        else:
            print(f"ℹ️  Qualifier exists: {qual.name} (id={qual.id})")

        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                username="admin",
                email="admin@demo.si",
                hashed_password=hash_password("test123"),
                role="org_admin",
                organization_id=org.id,
                is_active=True,
            )
            db.add(admin)
            db.commit()
            print(f"✅ Created admin user: admin / test123")
        else:
            print(f"ℹ️  Admin user exists: {admin.username}")

        print("\n✅ Demo data ready.")
        print(f"   Org slug: demo")
        print(f"   Login: admin / test123")

    except Exception as e:
        db.rollback()
        print(f"❌ Failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    ensure_demo()
