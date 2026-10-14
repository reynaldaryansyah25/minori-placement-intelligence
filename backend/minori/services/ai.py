"""Read-only AI use cases grounded in source evidence and official matching facts."""

import hashlib
import json
import re
from dataclasses import asdict
from datetime import UTC, datetime

from minori.domain.ai import AiOutputError
from minori.domain.errors import RecordNotFoundError
from minori.domain.matching_engine import MatchingEngine


class AiService:
    def __init__(self, ports, gateway, clock=lambda: datetime.now(UTC)):
        self.ports = ports
        self.gateway = gateway
        self.clock = clock

    def analyze(self, text):
        if not text.strip() or len(text) > 12000:
            raise ValueError("Gunakan teks antara 1 dan 12.000 karakter.")
        result = self.gateway.generate("vacancy", {"source_text": text})
        extraction = result["extraction"]
        evidence = extraction["evidence"]
        if any(item["quote"] not in text for item in [*evidence, *result["review"]["evidence"]]):
            raise AiOutputError(
                "Bukti AI tidak ditemukan dalam sumber. Tinjau dokumen atau analisis ulang."
            )
        evidenced = {item["field"] for item in evidence}
        for field, value in list(extraction.items()):
            if field in {"evidence", "missing_fields", "ambiguities"}:
                continue
            if value not in (None, []) and field not in evidenced:
                extraction[field] = [] if isinstance(value, list) else None
                extraction["missing_fields"].append(field)
            if extraction[field] in (None, []) and field not in extraction["missing_fields"]:
                extraction["missing_fields"].append(field)
        # A Japanese JLPT quote cannot silently be converted into JFT-Basic or vice versa.
        quotes = " ".join(
            x["quote"] for x in evidence if x["field"] == "language_requirements"
        ).lower()
        for requirement in extraction["language_requirements"]:
            markers = (
                ("jlpt", "日本語能力試験", "n1", "n2", "n3", "n4", "n5")
                if requirement["test_type"] == "jlpt"
                else ("jft", "国際交流基金日本語基礎テスト")
            )
            if not any(marker in quotes for marker in markers):
                raise AiOutputError(
                    "Jenis tes bahasa tidak didukung bukti sumber. Perlu konfirmasi."
                )
            if requirement["minimum_level"].casefold() not in quotes:
                raise AiOutputError("Tingkat bahasa tidak didukung bukti sumber. Perlu konfirmasi.")
        for field in ("quota", "minimum_experience_months"):
            value = extraction[field]
            if value is None:
                continue
            field_quotes = " ".join(item["quote"] for item in evidence if item["field"] == field)
            supported = bool(re.search(r"(?<!\d)" + str(value) + r"(?!\d)", field_quotes))
            if field == "minimum_experience_months":
                supported |= any(
                    int(years) * 12 == value
                    for years in re.findall(r"(\d+)\s*(?:年|tahun)", field_quotes)
                )
            if not supported:
                extraction[field] = None
                extraction["missing_fields"].append(field)
        extraction["missing_fields"] = list(dict.fromkeys(extraction["missing_fields"]))
        return result

    def explain(self, candidate_id, vacancy_id):
        candidate = self.ports.candidate.get(candidate_id)
        vacancy = self.ports.vacancy.get(vacancy_id)
        if candidate is None or vacancy is None:
            raise RecordNotFoundError("Kandidat atau lowongan tidak ditemukan.")
        match = self.ports.match.get_by_pair(candidate_id, vacancy_id)
        evaluation = MatchingEngine().evaluate(candidate, vacancy, self.clock())
        official = {
            "input_fingerprint": evaluation.input_fingerprint,
            "eligibility_status": evaluation.eligibility_status.value,
            "total_score": evaluation.total_score,
            "explanation": evaluation.explanation,
            "staff_status": match.status.value if match else "proposed",
        }
        # No candidate name, contact, domicile, employer history or database identifiers.
        facts = {
            "official": {
                **official,
                "score_for_staff": round(evaluation.total_score * 100, 1)
                if evaluation.total_score is not None
                else None,
                "score_maximum": 100,
            },
            "candidate": {
                "skills": candidate.skills,
                "preferred_program": candidate.preferred_program,
                "language_tests": [asdict(x) for x in candidate.language_tests],
                "certifications": [x.code for x in candidate.certifications],
            },
            "vacancy": {
                key: value
                for key, value in asdict(vacancy).items()
                if key not in {"id", "created_at", "updated_at", "reference", "employer_name"}
            },
        }
        narrative = self.gateway.generate("matching", facts)
        if evaluation.total_score is None and re.search(
            r"(?:skor|score|nilai)\D{0,15}\d", json.dumps(narrative), re.I
        ):
            raise AiOutputError("AI menyebut skor yang tidak dihitung. Gunakan hasil resmi.")
        if evaluation.total_score is not None:
            scores = re.findall(
                r"(?:skor|score)\D{0,40}(\d+(?:[.,]\d+)?)",
                json.dumps(narrative, ensure_ascii=False),
                re.I,
            )
            expected = facts["official"]["score_for_staff"]
            if any(abs(float(value.replace(",", ".")) - expected) > 0.051 for value in scores):
                raise AiOutputError("Penyebutan skor AI tidak sesuai hasil resmi pada skala 0–100.")
        digest = hashlib.sha256(json.dumps(facts, sort_keys=True, default=str).encode()).hexdigest()
        return {"official": official, "narrative": narrative, "facts_fingerprint": digest}
