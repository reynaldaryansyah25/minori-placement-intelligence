"""Synthetic demo composition through validated repositories and actual business operations."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from minori.db.inspection import inspect_database
from minori.db.session import immediate_transaction
from minori.domain.catalogs import MatchStatus, PlacementStepStatus, PlacementStepType
from minori.domain.entities import PlacementStageData
from minori.domain.reminders import ReminderPolicy
from minori.repositories.provider import provide_repositories
from minori.schemas.candidate import CandidateCreate
from minori.schemas.vacancy import VacancyCreate, VacancyDraftCreate
from minori.services.matching import MatchingService
from minori.services.placements import PlacementService
from minori.services.reminders import ReminderService

NAMES = [
    "Andi Pratama",
    "Siti Lestari",
    "Budi Santoso",
    "Dewi Anggraini",
    "Rizky Saputra",
    "Nur Aisyah",
    "Dimas Wicaksono",
    "Rina Maharani",
    "Arif Setiawan",
    "Putri Handayani",
    "Fajar Hidayat",
    "Nadia Permatasari",
    "Yoga Firmansyah",
    "Intan Puspitasari",
    "Reza Maulana",
    "Maya Kartika",
    "Aditya Nugraha",
    "Fitri Rahmawati",
    "Bayu Kurniawan",
    "Wulan Safitri",
    "Ilham Ramadhan",
    "Ratna Kusumawati",
    "Agus Hermawan",
    "Laila Zahra",
]
JOBS = [
    ("Staf budidaya sayuran", "agriculture", "Hokkaido", "crop_care"),
    ("Operator pengolahan pangan", "food_processing", "Aichi", "food_safety"),
    ("Pendamping lansia", "nursing_care", "Osaka", "elderly_care"),
    ("Teknisi pengelasan", "manufacturing", "Shizuoka", "welding"),
    ("Staf layanan hotel", "hospitality", "Kyoto", "hospitality_service"),
    ("Staf perawatan gedung", "building_cleaning", "Tokyo", "building_cleaning"),
    ("Staf konstruksi", "construction", "Kanagawa", "construction_safety"),
    ("Teknisi otomotif", "automobile_maintenance", "Saitama", "automotive_maintenance"),
    ("Staf perikanan", "fishery", "Miyagi", "fish_handling"),
    ("Staf layanan restoran", "food_service", "Fukuoka", "restaurant_service"),
]


def seed_professional_demo(database, *, anchor=None, dry_run=True):
    anchor = anchor or datetime.now(UTC)
    if anchor.tzinfo is None:
        raise ValueError("Anchor requires timezone")
    policy = ReminderPolicy(dry_run=dry_run, notification_delivery_mode="mailpit")

    def clock():
        return anchor

    def operation(callback):
        with database.session_factory() as session:
            ports = provide_repositories(session)

            def transaction():
                return immediate_transaction(session)

            reminder = ReminderService(ports, transaction, policy, clock)
            placement = PlacementService(ports, transaction, reminder, clock)
            return callback(session, ports, reminder, placement)

    candidates, vacancies = [], []
    for index, (title, sector, prefecture, skill) in enumerate(JOBS):
        reference = f"DEMO-PRO-VAC-{index + 1:02}"
        language = (
            {"test_type": "jlpt", "minimum_level": "N4"}
            if index % 2 == 0
            else {"test_type": "jft_basic", "minimum_level": "A2.2"}
        )
        data = VacancyCreate(
            reference=reference,
            title=title,
            employer_name=f"Minori Demo {prefecture} {index + 1:02} KK (Sintetis)",
            program="ssw",
            sector=sector,
            prefecture=prefecture,
            quota=3,
            minimum_experience_months=12,
            required_skills=[skill],
            preferred_skills=["teamwork"],
            required_certifications=[skill + "_certificate"],
            language_requirements=[language],
            application_deadline=anchor + timedelta(days=90),
        ).to_domain()
        existing = operation(
            lambda s, p, r, a, reference=reference: p.vacancy.get_by_reference(reference)
        )
        if not existing:

            def create(s, p, r, a, data=data):
                with immediate_transaction(s):
                    return p.vacancy.create(data)

            existing = operation(create)
        vacancies.append(existing)
    for index, name in enumerate(NAMES):
        _, sector, prefecture, skill = JOBS[index % 10]
        reference = f"DEMO-PRO-CAND-{index + 1:02}"
        test_type = "jlpt" if index % 10 % 2 == 0 else "jft_basic"
        level = ("N5" if index >= 20 else "N4") if test_type == "jlpt" else "A2.2"
        candidate = CandidateCreate(
            reference=reference,
            full_name=name,
            preferred_program="ssw",
            education_level="SMK",
            domicile_city=["Bandung", "Semarang", "Surabaya", "Yogyakarta"][index % 4],
            email=f"kandidat-{index + 1:02}@minori.invalid",
            email_verified=False,
            email_consent=False,
            status="preparing" if 16 <= index < 20 else "ready",
            skills=[] if index >= 20 else [skill, "teamwork"],
            preferred_prefectures=[prefecture],
            language_tests=[
                {
                    "test_type": test_type,
                    "level": level,
                    "taken_on": (anchor - timedelta(days=100)).date(),
                    "score": 130 if test_type == "jlpt" else 230,
                }
            ],
            certifications=[
                {
                    "code": skill + "_certificate",
                    "name": "Sertifikat Pelatihan Demo (Sintetis)",
                    "issuer": "Lembaga Latihan Demo Sintetis",
                    "issued_on": (anchor - timedelta(days=500)).date(),
                    "expires_on": (anchor + timedelta(days=730)).date(),
                }
            ],
            experiences=[
                {
                    "employer_name": "PT Pelatihan Demo Nusantara (Sintetis)",
                    "sector": sector,
                    "role": "Staf operasional demo",
                    "started_on": (anchor - timedelta(days=900)).date(),
                    "ended_on": (anchor - timedelta(days=100)).date(),
                }
            ],
        ).to_domain()
        existing = operation(
            lambda s, p, r, a, reference=reference: p.candidate.get_by_reference(reference)
        )
        if not existing:

            def create(s, p, r, a, candidate=candidate):
                with immediate_transaction(s):
                    return p.candidate.create(candidate)

            existing = operation(create)
        candidates.append(existing)

    def evaluate(s, p, r, a):
        return MatchingService(
            p.candidate, p.vacancy, p.match, p.evaluation, lambda: immediate_transaction(s), clock
        ).evaluate()

    evaluations = operation(evaluate)
    placements = []
    local = anchor.astimezone(ZoneInfo("Asia/Jakarta"))
    before = local.hour < 9
    for index in range(8):
        reference = f"DEMO-PRO-PLC-{index + 1:02}"
        existing = operation(
            lambda s, p, r, a, reference=reference: p.placement.get_by_reference(reference)
        )
        if not existing:
            decision = operation(
                lambda s, p, r, a, index=index: a.decide(
                    candidates[index].id, vacancies[index].id, MatchStatus.APPROVED, "staff.demo"
                )
            )
            existing = operation(
                lambda s, p, r, a, reference=reference, decision=decision: a.create(
                    reference, decision.id, "staff.demo"
                )
            )
            for seq, kind in enumerate(
                [PlacementStepType.INTERVIEW, PlacementStepType.MEDICAL_CHECK], 1
            ):
                days = (
                    (2 if before else 3)
                    if index == 0 and kind == PlacementStepType.INTERVIEW
                    else (0 if before else 1)
                    if index == 1 and kind == PlacementStepType.MEDICAL_CHECK
                    else 7 + index + seq
                )
                when = (local + timedelta(days=days)).replace(
                    hour=14, minute=0, second=0, microsecond=0
                )
                activity = PlacementStageData(
                    placement_id=existing.id,
                    code=kind.value.upper(),
                    step_type=kind,
                    sequence_number=seq,
                    status=PlacementStepStatus.SCHEDULED,
                    scheduled_at=when,
                    location=f"Ruang Demo MINORI {index + 1:02} (Sintetis)",
                )
                operation(
                    lambda s, p, r, a, existing=existing, activity=activity: a.create_activity(
                        existing.id, activity, "staff.demo"
                    )
                )
        placements.append(existing)
    for index in range(3):
        reference = f"DEMO-PRO-DRAFT-{index + 1:02}"
        existing = operation(
            lambda s, p, r, a, reference=reference: p.vacancy_draft.get_by_reference(reference)
        )
        if not existing:
            from dataclasses import asdict

            from minori.domain.entities import VacancyData
            from minori.domain.operations import record_data

            proposed = asdict(record_data(vacancies[8 + index % 2], VacancyData))
            proposed["reference"] = f"DEMO-PRO-PENDING-{index + 1:02}"
            draft = VacancyDraftCreate(
                reference=reference,
                source_channel="manual",
                source_reference=f"Penawaran demo sintetis {index + 1:02} untuk tinjauan staf",
                proposed_data=proposed,
            ).to_domain()

            def create(s, p, r, a, draft=draft):
                with immediate_transaction(s):
                    return p.vacancy_draft.create(draft)

            operation(create)
    inspection = inspect_database(database)
    counts = {}
    for ev in evaluations:
        value = ev["eligibility_status"]
        counts[str(value)] = counts.get(str(value), 0) + 1
    return {
        "synthetic": True,
        "anchor": anchor.isoformat(),
        "counts": inspection["counts"],
        "eligibility_counts": counts,
        "due_count": len(operation(lambda s, p, r, a: r.due())),
        "integrity": inspection["integrity"],
    }
