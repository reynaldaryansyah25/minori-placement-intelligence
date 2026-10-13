"""Bounded employer-relative utility, used for ranking only after eligibility passes."""

from datetime import date

from minori.domain.catalogs import CandidateStatus
from minori.domain.eligibility import valid_certification_codes
from minori.domain.entities import CandidateData, VacancyData
from minori.domain.matching import SCORING_WEIGHTS, EligibilityResult, ScoreComponent


class WeightedScoringEngine:
    def score(
        self,
        candidate: CandidateData,
        vacancy: VacancyData,
        eligibility: EligibilityResult,
        on: date,
    ) -> tuple[ScoreComponent, ...]:
        components = []
        weights = dict(SCORING_WEIGHTS)

        def add(name, weight, score, formula, **evidence):
            score = round(min(1.0, max(0.0, score)), 6)
            components.append(
                ScoreComponent(
                    name=name,
                    weight=weight,
                    score=score,
                    contribution=round(weight * score, 8),
                    formula=formula,
                    evidence=evidence,
                )
            )

        add(
            "language",
            weights["language"],
            eligibility.language_score,
            "0.6 + 0.4 * surplus_levels / remaining_levels; remaining=0 => 0.6; "
            "no requirement => 1",
            **eligibility.language_evidence,
        )
        target = max(24, 2 * vacancy.minimum_experience_months)
        add(
            "experience",
            weights["experience"],
            eligibility.relevant_months / target,
            "min(1, unique_relevant_days / (365.2425 / 12) / max(24, 2 * minimum_months))",
            unique_days=eligibility.relevant_days,
            months=round(eligibility.relevant_months, 6),
            target_months=target,
        )
        valid = valid_certification_codes(candidate, on)
        skills = sorted(set(vacancy.preferred_skills) - set(vacancy.required_skills))
        certs = sorted(set(vacancy.preferred_certifications) - set(vacancy.required_certifications))
        skill_fraction = len(set(skills) & set(candidate.skills)) / len(skills) if skills else 1.0
        cert_fraction = len(set(certs) & valid) / len(certs) if certs else 1.0
        add(
            "additional_qualifications",
            weights["additional_qualifications"],
            0.5 * skill_fraction + 0.5 * cert_fraction,
            "0.5 * preferred_skill_coverage + 0.5 * valid_preferred_certificate_coverage; "
            "empty => 1",
            preferred_skills=skills,
            preferred_certifications=certs,
            matched_skills=sorted(set(skills) & set(candidate.skills)),
            matched_certifications=sorted(set(certs) & valid),
            skill_coverage=skill_fraction,
            certification_coverage=cert_fraction,
        )
        location = (
            float(
                vacancy.prefecture.casefold()
                in {item.casefold() for item in candidate.preferred_prefectures}
            )
            if candidate.preferred_prefectures
            else 0.5
        )
        readiness = {
            CandidateStatus.READY: 1.0,
            CandidateStatus.PREPARING: 0.5,
            CandidateStatus.REGISTERED: 0.0,
            CandidateStatus.INACTIVE: 0.0,
        }[candidate.status]
        program = float(candidate.preferred_program == vacancy.program)
        add(
            "preference_readiness",
            weights["preference_readiness"],
            0.4 * program + 0.3 * location + 0.3 * readiness,
            "0.4 * program_agreement + 0.3 * prefecture_agreement + 0.3 * readiness",
            program_agreement=program,
            prefecture_agreement=location,
            readiness=readiness,
        )
        return tuple(components)
