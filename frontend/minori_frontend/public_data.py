"""Read-only HTTP projection restricted to the verified synthetic seed catalog."""

import hashlib
import json
from collections import Counter

OMITTED = {
    "id",
    "reference",
    "status",
    "created_at",
    "updated_at",
    "email",
    "email_verified",
    "email_consent",
    "taken_on",
    "issued_on",
    "expires_on",
    "started_on",
    "ended_on",
    "application_deadline",
    "analysis_metadata",
    "reviewed_at",
    "published_vacancy_id",
}


def profile_digest(value):
    def normalize(item):
        if isinstance(item, dict):
            return {k: normalize(v) for k, v in item.items() if k not in OMITTED}
        if isinstance(item, list):
            return [normalize(v) for v in item]
        return item

    return hashlib.sha256(
        json.dumps(normalize(value), sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def without_private(value):
    if isinstance(value, dict):
        return {
            k: without_private(v)
            for k, v in value.items()
            if k
            not in {
                "email",
                "email_verified",
                "email_consent",
                "approved_message",
                "approved_by",
                "approval_key",
                "claim_token_hash",
                "provider_reference",
                "analysis_metadata",
                "schedule_context",
                "recipient_reference",
                "facts_fingerprint",
                "actor_reference",
            }
        }
    if isinstance(value, list):
        return [without_private(v) for v in value]
    return value


class PublicDemoData:
    def __init__(self, fetch):
        from minori_frontend.public_catalog import CATALOG

        self.catalog = CATALOG
        self.fetch = fetch
        self.cache = {}

    def _all(self, path):
        rows = []
        for _ in range(100):
            page = self.fetch("GET", path, params={"limit": 100, "offset": len(rows)})
            rows.extend(page)
            if len(page) < 100:
                return rows
        raise ValueError("Public data limit exceeded")

    def roots(self, kind):
        if kind not in self.cache:
            path = {
                "candidates": "/candidates",
                "vacancies": "/vacancies",
                "drafts": "/vacancies/drafts",
            }[kind]
            allowed = self.catalog[kind]
            self.cache[kind] = [
                without_private(r)
                for r in self._all(path)
                if allowed.get(r.get("reference")) == profile_digest(r)
            ]
        return self.cache[kind]

    def placements(self):
        if "placements" not in self.cache:
            candidates = {r["reference"]: r["id"] for r in self.roots("candidates")}
            vacancies = {r["reference"]: r["id"] for r in self.roots("vacancies")}
            allowed = {
                f"DEMO-PRO-PLC-{i:02}": (
                    candidates.get(f"DEMO-PRO-CAND-{i:02}"),
                    vacancies.get(f"DEMO-PRO-VAC-{i:02}"),
                )
                for i in range(1, 9)
            }
            self.cache["placements"] = [
                without_private(r)
                for r in self._all("/placements")
                if allowed.get(r.get("reference")) == (r.get("candidate_id"), r.get("vacancy_id"))
                and r.get("candidate_id")
                and r.get("vacancy_id")
            ]
        return self.cache["placements"]

    def activities(self, placement_id):
        key = "activities:" + placement_id
        if key not in self.cache:
            placement = next((p for p in self.placements() if p["id"] == placement_id), None)
            if placement is None:
                return []
            number = int(placement["reference"].rsplit("-", 1)[1])
            self.cache[key] = [
                without_private(a)
                for a in self.fetch("GET", f"/placements/{placement_id}/activities")
                if a.get("placement_id") == placement_id
                and a.get("location") == f"Ruang Demo MINORI {number:02} (Sintetis)"
                and a.get("code") == a.get("step_type", "").upper()
            ]
        return self.cache[key]

    def reminders(self):
        if "reminders" not in self.cache:
            placements = {p["id"]: p for p in self.placements()}
            activities = {a["id"] for pid in placements for a in self.activities(pid)}
            self.cache["reminders"] = [
                without_private(r)
                for r in self._all("/reminders")
                if r.get("placement_stage_id") in activities
                and r.get("placement_id") in placements
                and r.get("candidate_id") == placements[r["placement_id"]]["candidate_id"]
            ]
        return self.cache["reminders"]

    def matches(self, vacancy_id=None, ranking=False):
        candidates = {c["id"] for c in self.roots("candidates")}
        vacancies = {v["id"] for v in self.roots("vacancies")}
        if vacancy_id and vacancy_id not in vacancies:
            return []
        rows = []
        for vid in [vacancy_id] if vacancy_id else vacancies:
            key = ("ranking:" if ranking else "matching:") + vid
            if key not in self.cache:
                path = f"/matching/vacancies/{vid}/" + ("ranking" if ranking else "candidates")
                self.cache[key] = [
                    without_private(r)
                    for r in self._all(path)
                    if r.get("candidate_id") in candidates and r.get("vacancy_id") == vid
                ]
            rows.extend(self.cache[key])
        return rows

    def summary(self):
        candidates, vacancies, placements, reminders, matches = (
            self.roots("candidates"),
            self.roots("vacancies"),
            self.placements(),
            self.reminders(),
            self.matches(),
        )
        eligibility = Counter(r["eligibility_status"] for r in matches)
        counts = Counter(r["status"] for r in reminders)
        return {
            "total_candidates": len(candidates),
            "ready_candidates": sum(c["status"] == "ready" for c in candidates),
            "active_vacancies": sum(v["status"] == "open" for v in vacancies),
            "active_placements": sum(
                p["status"] in {"preparing", "in_progress"} for p in placements
            ),
            "eligible_matches": eligibility["ELIGIBLE"],
            "needs_review_matches": eligibility["NEEDS_REVIEW"],
            "not_eligible_matches": eligibility["NOT_ELIGIBLE"],
            "pending_reminders": counts["pending"],
            "sent_reminders": counts["sent"],
            "simulated_reminders": counts["simulated"],
            "failed_reminders": counts["failed"],
            "missed_reminders": counts["missed"],
            "placements_by_status": dict(Counter(p["status"] for p in placements)),
            "upcoming_activities": sorted(
                [
                    a
                    for p in placements
                    for a in self.activities(p["id"])
                    if a.get("scheduled_at") and a["status"] in {"scheduled", "in_progress"}
                ],
                key=lambda a: a["scheduled_at"],
            )[:5],
            # Staff audit payloads and actors are not part of the public projection.
            "recent_audits": [],
        }

    @staticmethod
    def _page(rows, params):
        params = params or {}
        selected = rows
        for key in (
            "candidate_id",
            "vacancy_id",
            "placement_id",
            "status",
            "preferred_program",
            "program",
        ):
            if params.get(key) is not None:
                selected = [r for r in selected if str(r.get(key)) == str(params[key])]
        if params.get("query"):
            term = str(params["query"]).casefold()
            selected = [
                r
                for r in selected
                if term
                in " ".join(
                    str(r.get(k, ""))
                    for k in ("full_name", "title", "employer_name", "domicile_city")
                ).casefold()
            ]
        start = int(params.get("offset", 0))
        return selected[start : start + int(params.get("limit", 100))]

    def request(self, path, params=None):
        from minori_frontend.api_client import ApiClientError

        if path == "/overview/summary":
            return self.summary()
        roots = {
            "/candidates": "candidates",
            "/vacancies": "vacancies",
            "/vacancies/drafts": "drafts",
        }
        if path in roots:
            return self._page(self.roots(roots[path]), params)
        if path == "/placements":
            return self._page(self.placements(), params)
        if path == "/reminders":
            return self._page(self.reminders(), params)
        if path == "/matching/results":
            return self._page(self.matches(), params)
        if path == "/placements/approved-candidates":
            candidates = {c["id"]: c for c in self.roots("candidates")}
            vacancies = {v["id"]: v for v in self.roots("vacancies")}
            return self._page(
                [
                    r
                    for r in self._all(path)
                    if r.get("candidate_id") in candidates
                    and r.get("vacancy_id") in vacancies
                    and r.get("candidate_name") == candidates[r["candidate_id"]]["full_name"]
                    and r.get("vacancy_title") == vacancies[r["vacancy_id"]]["title"]
                ],
                params,
            )
        parts = path.strip("/").split("/")
        if len(parts) == 2 and parts[0] in {"candidates", "vacancies", "placements", "reminders"}:
            rows = (
                self.roots(parts[0])
                if parts[0] in {"candidates", "vacancies"}
                else getattr(self, parts[0])()
            )
            row = next((r for r in rows if r["id"] == parts[1]), None)
            if row:
                return row
        if len(parts) == 3 and parts[0] == "placements" and parts[2] == "activities":
            return self.activities(parts[1])
        if (
            len(parts) == 3
            and parts[0] == "reminders"
            and any(r["id"] == parts[1] for r in self.reminders())
        ):
            if parts[2] == "routing":
                return None
            if parts[2] == "attempts":
                keys = {"attempt_number", "status", "attempted_at", "finished_at", "error_code"}
                return [
                    {k: r[k] for k in keys if k in r}
                    for r in self.fetch("GET", path, params=params)
                ]
        if (
            len(parts) == 4
            and parts[:2] == ["matching", "vacancies"]
            and parts[3] in {"ranking", "candidates"}
        ):
            return self._page(self.matches(parts[2], ranking=parts[3] == "ranking"), params)
        if (
            len(parts) == 6
            and parts[:2] == ["matching", "candidates"]
            and parts[3] == "vacancies"
            and parts[5] == "explanation"
        ):
            row = next((r for r in self.matches(parts[4]) if r["candidate_id"] == parts[2]), None)
            if row:
                return row
        raise ApiClientError(403, "Data ini tidak tersedia pada demo publik.")
