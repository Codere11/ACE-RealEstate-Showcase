"""
Weighted demographics sampler for the ACE simulation script.

Every dimension is sampled independently with cumulative tracking so the
final distribution across all 100 conversations matches the target percentages.
Each draw reduces the weight for that bucket, steering later draws toward
underrepresented buckets. Quirks are sampled independently and cross-mixed.

Usage:
    sampler = DemographicsSampler(person_pool, target_counts)
    for i in range(100):
        profile = sampler.draw()
        print(profile)
    sampler.summary()  # print distribution report
"""

import json
import random
from pathlib import Path
from typing import Any

# ═══════════════════════════════════════════════════════════
#  Distribution targets (from Analize.md)
# ═══════════════════════════════════════════════════════════

AGE_BUCKETS = [
    ("18-24", 0.15),
    ("25-34", 0.35),
    ("35-44", 0.30),
    ("45-54", 0.12),
    ("55+",  0.08),
]

GENDER_BUCKETS = [
    ("ženska", 0.92),
    ("moški",  0.08),
]

CUSTOMER_TYPE_BUCKETS = [
    ("nova stranka",     0.60),
    ("vračajoča stranka", 0.40),
]

SERVICE_INTEREST_BUCKETS = [
    ("nega obraza",      0.30),
    ("maska obraza",     0.25),
    ("čiščenje obraza",  0.20),
    ("nohti",            0.15),
    ("trajno ličenje",   0.10),
]

CHANNEL_BUCKETS = [
    ("Instagram",   0.35),
    ("priporočilo", 0.25),
    ("Google",      0.20),
    ("mimoidoči",   0.15),
    ("Facebook",    0.05),
]

BUDGET_BUCKETS = [
    ("srednja", 0.50),
    ("visoka — občutljiv/a na ceno",  0.30),
    ("nizka — premium kupec",         0.20),
]

DISPOSITION_BUCKETS = [
    ("samo brskam, nisem prepričan/a če bom kaj rezerviral/a", 0.38),
    ("raziskujem, načrtujem, rabim še informacije",             0.32),
    ("pripravljen/a rezervirati zdaj",                          0.25),
    ("vem kaj hočem, želim najboljše kar imate",                0.05),
]

QUIRK_BUCKETS = [
    ("nobena",                             0.70),
    ("osebje",                             0.10),  # might request staff
    ("plačilo",                            0.10),  # payment anxiety
    ("VIP / zahtevna",                     0.05),  # demanding
    ("negotov/a — možnost no-show",        0.05),  # flaky
]

# ═══════════════════════════════════════════════════════════
#  Distribution tracker
# ═══════════════════════════════════════════════════════════

class DistributionTracker:
    """Tracks cumulative draws and weights next draw toward underrepresented buckets."""

    def __init__(self, buckets: list[tuple[str, float]], label: str):
        self.label = label
        self.buckets = buckets
        self.counts: dict[str, int] = {b[0]: 0 for b in buckets}
        self.total = 0

    def _weights(self) -> list[str]:
        """Return a weighted list of bucket keys. Underdrawn buckets get more weight."""
        if self.total == 0:
            # First draw: pure target percentages
            return self._flat_weights(self.buckets)

        # Calculate how far behind each bucket is vs target
        parts = []
        for key, target_pct in self.buckets:
            actual_pct = self.counts[key] / self.total if self.total > 0 else 0
            deficit = max(0.0, target_pct - actual_pct)
            # Weight = target + deficit boost (up to 3x for severely underdrawn)
            weight = target_pct + deficit * 3.0
            parts.append((key, max(0.01, weight)))

        return self._flat_weights(parts)

    @staticmethod
    def _flat_weights(parts: list[tuple[str, float]]) -> list[str]:
        """Expand (key, weight) pairs into a flat list for random.choice."""
        flat = []
        for key, w in parts:
            flat.extend([key] * max(1, int(w * 100)))
        if not flat:
            return [parts[0][0]]
        return flat

    def draw(self) -> str:
        """Draw a single value, track it, return the key."""
        key = random.choice(self._weights())
        self.counts[key] += 1
        self.total += 1
        return key

    def report(self) -> dict:
        """Return {key: (count, target_pct, actual_pct)} for summary."""
        out = {}
        for key, target in self.buckets:
            actual = self.counts[key] / self.total if self.total > 0 else 0
            out[key] = {"count": self.counts[key], "target": target, "actual": round(actual, 3)}
        return out


# ═══════════════════════════════════════════════════════════
#  Sampler
# ═══════════════════════════════════════════════════════════

class DemographicsSampler:
    """Generates independent demographic profiles with weighted distribution tracking."""

    def __init__(self, pool_path: str = None):
        if pool_path is None:
            pool_path = Path(__file__).parent / "person_pool.json"
        with open(pool_path) as f:
            self.pool = json.load(f)

        self.used_names: set[str] = set()

        # Initialize trackers
        self.age = DistributionTracker(AGE_BUCKETS, "age")
        self.gender = DistributionTracker(GENDER_BUCKETS, "gender")
        self.customer_type = DistributionTracker(CUSTOMER_TYPE_BUCKETS, "customer_type")
        self.service = DistributionTracker(SERVICE_INTEREST_BUCKETS, "service")
        self.channel = DistributionTracker(CHANNEL_BUCKETS, "channel")
        self.budget = DistributionTracker(BUDGET_BUCKETS, "budget")
        self.disposition = DistributionTracker(DISPOSITION_BUCKETS, "disposition")
        self.quirk = DistributionTracker(QUIRK_BUCKETS, "quirk")

        self.all_trackers = [
            self.age, self.gender, self.customer_type, self.service,
            self.channel, self.budget, self.disposition, self.quirk,
        ]

    def _pick_name(self, gender: str) -> str:
        """Pick an unused name matching the gender."""
        if gender == "moški":
            pool = self.pool["male_names"]
        else:
            pool = self.pool["female_names"]

        available = [n for n in pool if n not in self.used_names]
        if not available:
            # If we exhausted the pool, reuse but append a number
            name = random.choice(pool)
            suffix = 2
            while f"{name} {suffix}" in self.used_names:
                suffix += 1
            name = f"{name} {suffix}"

        else:
            name = random.choice(available)

        self.used_names.add(name)
        return name

    def _pick_phone(self) -> str:
        return random.choice(self.pool["phones"])

    def _pick_email(self, name: str) -> str:
        first = name.lower().replace(" ", ".").replace("š", "s").replace("č", "c").replace("ž", "z")
        last = random.choice(self.pool["last_names"]).lower().replace("š", "s").replace("č", "c").replace("ž", "z")
        return f"{first}.{last}@gmail.com"

    def draw(self) -> dict[str, Any]:
        """
        Generate a single demographics card. All dimensions are independent draws.
        Returns a dict matching the format expected by the orchestrator.
        """
        gender = self.gender.draw()
        age_bucket = self.age.draw()
        name = self._pick_name(gender)

        # Map age bucket to a specific age
        age = self._map_age(age_bucket)

        profile = {
            "ime": name,
            "starost": age,
            "spol": gender,
            "kanal": self.channel.draw(),
            "nov_ali_vracajoc": self.customer_type.draw(),
            "zanima_jo": self.service.draw(),
            "obcutljivost_na_ceno": self.budget.draw(),
            "dispozicija": self.disposition.draw(),
            "posebnosti": self.quirk.draw(),
            "telefon": self._pick_phone(),
            "email": self._pick_email(name),
            "age_bucket": age_bucket,  # meta, not shown to LLM
        }
        return profile

    @staticmethod
    def _map_age(bucket: str) -> int:
        ranges = {
            "18-24": (18, 24),
            "25-34": (25, 34),
            "35-44": (35, 44),
            "45-54": (45, 54),
            "55+":   (55, 68),
        }
        lo, hi = ranges.get(bucket, (30, 40))
        return random.randint(lo, hi)

    def restore_from_results(self, results: list[dict]):
        """Re-feed previously completed profiles so distribution trackers are current."""
        age_map = {
            (18, 24): "18-24", (25, 34): "25-34", (35, 44): "35-44",
            (45, 54): "45-54", (55, 99): "55+",
        }
        for r in results:
            # Age bucket
            age = r.get("starost", 30)
            bucket = r.get("age_bucket") or next(v for (lo, hi), v in age_map.items() if lo <= age <= hi)
            self.age.counts[bucket] = self.age.counts.get(bucket, 0) + 1
            self.age.total += 1
            # Gender
            g = r.get("spol", "ženska")
            self.gender.counts[g] = self.gender.counts.get(g, 0) + 1
            self.gender.total += 1
            # Customer type
            ct = r.get("nov_ali_vracajoc", "nova stranka")
            self.customer_type.counts[ct] = self.customer_type.counts.get(ct, 0) + 1
            self.customer_type.total += 1
            # Service
            svc = r.get("zanima_jo", "nega obraza")
            self.service.counts[svc] = self.service.counts.get(svc, 0) + 1
            self.service.total += 1
            # Channel
            ch = r.get("kanal", "Instagram")
            self.channel.counts[ch] = self.channel.counts.get(ch, 0) + 1
            self.channel.total += 1
            # Budget
            b = r.get("obcutljivost_na_ceno", "srednja")
            self.budget.counts[b] = self.budget.counts.get(b, 0) + 1
            self.budget.total += 1
            # Disposition
            d = r.get("dispozicija", "")
            if d in self.disposition.counts:
                self.disposition.counts[d] += 1
            self.disposition.total += 1
            # Quirk
            q = r.get("posebnosti", "nobena")
            if q in self.quirk.counts:
                self.quirk.counts[q] += 1
            self.quirk.total += 1
            # Name tracking
            name = r.get("ime", "")
            if name:
                self.used_names.add(name)

    def summary(self) -> str:
        """Produce a readable distribution report."""
        lines = ["\n═══ DEMOGRAPHICS DISTRIBUTION ═══"]
        for t in self.all_trackers:
            lines.append(f"\n  {t.label}:")
            report = t.report()
            for key, d in report.items():
                bar = "█" * max(1, int(d["actual"] * 40))
                gap = "░" * max(0, int(d["target"] * 40) - int(d["actual"] * 40))
                lines.append(
                    f"    {key:<30s}  target={d['target']:.0%}  actual={d['actual']:.0%}  "
                    f"(n={d['count']})  {bar}{gap}"
                )
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
#  Quick test
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    sampler = DemographicsSampler()
    for i in range(5):
        p = sampler.draw()
        print(f"\n#{i+1} {p['ime']} ({p['starost']}, {p['spol']})")
        for k, v in p.items():
            if k not in ("ime", "starost", "spol", "age_bucket"):
                print(f"  {k}: {v}")
    print(sampler.summary())
