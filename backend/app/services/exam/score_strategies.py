"""
SIMS Plus - Curriculum-Specific Score Calculation Strategies

Strategy pattern for computing subject scores, grades, and aggregates
across different educational frameworks (GES, Cambridge, American, IB,
French, Montessori). Each strategy encapsulates the scoring rules for
its curriculum so the report engine can dispatch without conditionals.
"""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any

from app.models.academic import Grade
from app.models.curriculum import AssessmentComponent, CurriculumProfile


class SubjectScoreResult:
    """Result of scoring a single subject for a student."""

    def __init__(self):
        self.component_scores: dict[str, Decimal | None] = {}
        self.raw_total: Decimal | None = None
        self.weighted_total: Decimal | None = None
        # Legacy GES columns -- populated by GESScoreStrategy for backward compat
        self.class_score: Decimal | None = None
        self.exams_score: Decimal | None = None
        self.final_score: Decimal | None = None
        self.grade: str | None = None
        self.grade_point: Decimal | None = None
        self.grade_remark: str | None = None
        # Montessori -- narrative instead of numeric
        self.narrative: str | None = None
        # Cambridge -- optional effort grade alongside academic grade
        self.effort_grade: str | None = None


class ScoreStrategy(ABC):
    """Base class for curriculum-specific score calculation."""

    @abstractmethod
    def calculate_subject_score(
        self,
        component_scores: dict[str, Decimal | None],
        components: list[AssessmentComponent],
        max_scores: dict[str, Decimal],
    ) -> SubjectScoreResult:
        """
        Calculate a single subject score from individual component scores.

        Args:
            component_scores: Mapping of component_type -> raw score
            components: Assessment component definitions with weights
            max_scores: Mapping of component_type -> maximum possible score
        """
        ...

    @abstractmethod
    def determine_grade(
        self, score: Decimal | None, grades: list[Grade]
    ) -> tuple[str | None, Decimal | None, str | None]:
        """
        Determine grade, grade_point, and remark from a final score.

        Returns (grade_label, grade_point, remark).
        """
        ...

    def calculate_aggregate(
        self,
        subject_results: list[SubjectScoreResult],
        profile: CurriculumProfile,
    ) -> dict[str, Any]:
        """
        Calculate curriculum-level aggregate metrics (GPA, IB total, etc.).

        Default implementation returns empty dict -- overridden by
        curricula that produce aggregates.
        """
        return {}


# =========================
# GES Strategy
# =========================


class GESScoreStrategy(ScoreStrategy):
    """
    Ghana Education Service scoring.

    Uses CA/Exam split via maps_to_ca / maps_to_exam flags on components.
    Grading: WAEC A1-F9 scale based on percentage out of 100.
    """

    def calculate_subject_score(self, component_scores, components, max_scores):
        result = SubjectScoreResult()
        result.component_scores = component_scores

        ca_components = [c for c in components if c.maps_to_ca]
        exam_components = [c for c in components if c.maps_to_exam]

        # Aggregate raw CA scores and normalise to the CA weight band
        ca_weighted = Decimal("0")
        ca_max = Decimal("0")
        for comp in ca_components:
            score = component_scores.get(comp.component_type.value)
            max_s = max_scores.get(comp.component_type.value, Decimal("10"))
            if score is not None:
                ca_weighted += score
                ca_max += max_s

        # Aggregate raw exam scores and normalise to the exam weight band
        exam_weighted = Decimal("0")
        exam_max = Decimal("0")
        for comp in exam_components:
            score = component_scores.get(comp.component_type.value)
            max_s = max_scores.get(comp.component_type.value, Decimal("100"))
            if score is not None:
                exam_weighted += score
                exam_max += max_s

        ca_weight = sum(c.weight for c in ca_components)
        exam_weight = sum(c.weight for c in exam_components)

        if ca_max > 0:
            result.class_score = (ca_weighted / ca_max) * ca_weight
        else:
            result.class_score = Decimal("0")

        if exam_max > 0:
            result.exams_score = (exam_weighted / exam_max) * exam_weight
        else:
            result.exams_score = Decimal("0")

        result.final_score = result.class_score + result.exams_score
        return result

    def determine_grade(self, score, grades):
        if score is None:
            return (None, None, None)
        for grade in sorted(grades, key=lambda g: g.min_score, reverse=True):
            if score >= grade.min_score:
                return (grade.grade, grade.grade_point, grade.remark)
        return (None, None, None)


# =========================
# Cambridge / Edexcel Strategy
# =========================


class CambridgeScoreStrategy(ScoreStrategy):
    """
    Cambridge International / Edexcel scoring.

    Weighted average of components (no CA/Exam split).
    Grades: A*-G (IGCSE) or A*-E (A-Level), looked up from grading scale.
    Supports optional effort grades.
    """

    def calculate_subject_score(self, component_scores, components, max_scores):
        result = SubjectScoreResult()
        result.component_scores = component_scores

        total_weight = sum(c.weight for c in components)
        weighted_sum = Decimal("0")

        for comp in components:
            score = component_scores.get(comp.component_type.value)
            max_s = max_scores.get(comp.component_type.value, Decimal("100"))
            if score is not None and max_s > 0:
                # Normalise to weight band
                normalized = (score / max_s) * comp.weight
                weighted_sum += normalized

        if total_weight > 0:
            result.final_score = (weighted_sum / total_weight) * Decimal("100")
        else:
            result.final_score = Decimal("0")

        return result

    def determine_grade(self, score, grades):
        if score is None:
            return (None, None, None)
        for grade in sorted(grades, key=lambda g: g.min_score, reverse=True):
            if score >= grade.min_score:
                return (grade.grade, grade.grade_point, grade.remark)
        return (None, None, None)


# =========================
# American Strategy
# =========================


class AmericanScoreStrategy(ScoreStrategy):
    """
    US Common Core / AP scoring.

    Weighted average of components, GPA calculation, honor roll.
    """

    HONOR_ROLL_GPA = Decimal("3.5")

    def calculate_subject_score(self, component_scores, components, max_scores):
        result = SubjectScoreResult()
        result.component_scores = component_scores

        total_weight = sum(c.weight for c in components)
        weighted_sum = Decimal("0")

        for comp in components:
            score = component_scores.get(comp.component_type.value)
            max_s = max_scores.get(comp.component_type.value, Decimal("100"))
            if score is not None and max_s > 0:
                normalized = (score / max_s) * comp.weight
                weighted_sum += normalized

        if total_weight > 0:
            result.final_score = (weighted_sum / total_weight) * Decimal("100")
        else:
            result.final_score = Decimal("0")

        return result

    def determine_grade(self, score, grades):
        if score is None:
            return (None, None, None)
        for grade in sorted(grades, key=lambda g: g.min_score, reverse=True):
            if score >= grade.min_score:
                return (grade.grade, grade.grade_point, grade.remark)
        return (None, None, None)

    # AP/Honors GPA bonus caps
    AP_BONUS = Decimal("1.0")
    AP_CAP = Decimal("5.0")
    HONORS_BONUS = Decimal("0.5")
    HONORS_CAP = Decimal("4.5")

    def calculate_aggregate(self, subject_results, profile):
        total_points = Decimal("0")
        weighted_total_points = Decimal("0")
        total_credits = Decimal("0")
        credits_earned = Decimal("0")

        for result in subject_results:
            if result.grade_point is not None:
                # Default 1 credit per subject; real credits come from SubjectCurriculumMapping
                credit = Decimal("1")
                total_points += result.grade_point * credit
                total_credits += credit
                # A grade_point >= 1.0 means the course was passed
                if result.grade_point >= Decimal("1.0"):
                    credits_earned += credit

                # Weighted GPA: apply AP/Honors bonus from component_scores metadata
                # AP courses get +1.0 bonus (capped at 5.0), Honors get +0.5 (capped at 4.5)
                weighted_gp = result.grade_point
                course_level = result.component_scores.get("course_level")
                if course_level == "ap":
                    weighted_gp = min(
                        result.grade_point + self.AP_BONUS, self.AP_CAP
                    )
                elif course_level == "honors":
                    weighted_gp = min(
                        result.grade_point + self.HONORS_BONUS, self.HONORS_CAP
                    )
                weighted_total_points += weighted_gp * credit

        gpa = total_points / total_credits if total_credits > 0 else None
        weighted_gpa = weighted_total_points / total_credits if total_credits > 0 else None

        return {
            "gpa": round(gpa, 2) if gpa else None,
            "weighted_gpa": round(weighted_gpa, 2) if weighted_gpa else None,
            "total_credits_earned": credits_earned,
            "honor_roll": gpa >= self.HONOR_ROLL_GPA if gpa else False,
        }


# =========================
# IB Strategy
# =========================


class IBScoreStrategy(ScoreStrategy):
    """
    International Baccalaureate scoring (MYP/DP).

    Levels 1-7 per subject, total points out of 45 for DP.
    EE+TOK bonus (max 3 bonus points) added separately when available.
    """

    def calculate_subject_score(self, component_scores, components, max_scores):
        result = SubjectScoreResult()
        result.component_scores = component_scores

        total_weight = sum(c.weight for c in components)
        weighted_sum = Decimal("0")

        for comp in components:
            score = component_scores.get(comp.component_type.value)
            max_s = max_scores.get(comp.component_type.value, Decimal("100"))
            if score is not None and max_s > 0:
                normalized = (score / max_s) * comp.weight
                weighted_sum += normalized

        if total_weight > 0:
            result.final_score = (weighted_sum / total_weight) * Decimal("100")
        else:
            result.final_score = Decimal("0")

        return result

    def determine_grade(self, score, grades):
        if score is None:
            return (None, None, None)
        for grade in sorted(grades, key=lambda g: g.min_score, reverse=True):
            if score >= grade.min_score:
                return (grade.grade, grade.grade_point, grade.remark)
        return (None, None, None)

    def calculate_aggregate(self, subject_results, profile):
        total_points = 0
        for result in subject_results:
            if result.grade_point is not None:
                total_points += int(result.grade_point)

        # EE+TOK bonus (max 3 bonus points) is not calculated here;
        # it is added separately when EE/TOK scores are available.
        return {
            "ib_total_points": total_points,
        }


# =========================
# French Strategy
# =========================


class FrenchScoreStrategy(ScoreStrategy):
    """
    French Baccalaureate scoring.

    Coefficient-weighted system scored out of 20.
    Mention thresholds: Tres Bien (>=16), Bien (>=14), Assez Bien (>=12), Passable (>=10).
    """

    MENTIONS = [
        (Decimal("16"), "Tres Bien"),
        (Decimal("14"), "Bien"),
        (Decimal("12"), "Assez Bien"),
        (Decimal("10"), "Passable"),
    ]

    def calculate_subject_score(self, component_scores, components, max_scores):
        result = SubjectScoreResult()
        result.component_scores = component_scores

        total_weight = sum(c.weight for c in components)
        weighted_sum = Decimal("0")

        for comp in components:
            score = component_scores.get(comp.component_type.value)
            # French default max is 20, not 100
            max_s = max_scores.get(comp.component_type.value, Decimal("20"))
            if score is not None and max_s > 0:
                normalized = (score / max_s) * comp.weight
                weighted_sum += normalized

        if total_weight > 0:
            # Normalise to the 0-20 French scale
            result.final_score = (weighted_sum / total_weight) * Decimal("20")
        else:
            result.final_score = Decimal("0")

        return result

    def determine_grade(self, score, grades):
        if score is None:
            return (None, None, None)
        for grade in sorted(grades, key=lambda g: g.min_score, reverse=True):
            if score >= grade.min_score:
                return (grade.grade, grade.grade_point, grade.remark)
        return (None, None, None)

    def calculate_aggregate(self, subject_results, profile):
        total_weighted = Decimal("0")
        total_coeff = Decimal("0")

        for result in subject_results:
            # Default coefficient 1; real coefficients come from SubjectCurriculumMapping
            coeff = Decimal("1")
            if result.final_score is not None:
                total_weighted += result.final_score * coeff
                total_coeff += coeff

        avg = total_weighted / total_coeff if total_coeff > 0 else None

        mention = None
        if avg is not None:
            for threshold, label in self.MENTIONS:
                if avg >= threshold:
                    mention = label
                    break

        return {
            "french_mention": mention,
            "weighted_average": round(avg, 2) if avg is not None else None,
            "total_coefficients": total_coeff,
            "total_weighted_score": round(total_weighted, 2),
        }


# =========================
# Montessori Strategy
# =========================


class MontessoriScoreStrategy(ScoreStrategy):
    """
    Montessori narrative-based assessment.

    No numeric grades -- progress is tracked through observation narratives
    and developmental progress levels (emerging, developing, proficient, mastery).
    """

    PROGRESS_LEVELS = ["emerging", "developing", "practicing", "mastery"]

    def calculate_subject_score(self, component_scores, components, max_scores):
        result = SubjectScoreResult()
        result.component_scores = component_scores
        # Montessori does not produce a numeric total
        result.final_score = None
        return result

    def determine_grade(self, score, grades):
        # Montessori uses progress levels from config, not numeric grades
        return (None, None, None)

    def calculate_aggregate(self, subject_results, profile):
        return {}


# =========================
# Factory
# =========================


def get_score_strategy(curriculum_type: str) -> ScoreStrategy:
    """
    Factory function returning the appropriate strategy for a curriculum type.

    Falls back to GESScoreStrategy for unknown types so callers never
    receive None.
    """
    strategies: dict[str, type[ScoreStrategy]] = {
        "ges": GESScoreStrategy,
        "cambridge": CambridgeScoreStrategy,
        "edexcel": CambridgeScoreStrategy,  # Edexcel shares Cambridge scoring logic
        "american": AmericanScoreStrategy,
        "ib": IBScoreStrategy,
        "french": FrenchScoreStrategy,
        "montessori": MontessoriScoreStrategy,
        "custom": GESScoreStrategy,  # Custom defaults to GES-style
    }
    strategy_class = strategies.get(curriculum_type, GESScoreStrategy)
    return strategy_class()
