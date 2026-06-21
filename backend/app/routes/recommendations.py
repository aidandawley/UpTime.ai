from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.database import get_session
from app.models.recommendation import Recommendation

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


@router.get("/")
def list_recommendations(session: Session = Depends(get_session)):
    recommendations = session.exec(
        select(Recommendation).order_by(Recommendation.id.desc())
    ).all()
    return [
        recommendation
        for recommendation in recommendations
        if not _contains_malformed_model_artifacts(recommendation)
    ]


def _contains_malformed_model_artifacts(recommendation: Recommendation) -> bool:
    text = " ".join(
        [
            recommendation.title,
            recommendation.summary,
            recommendation.justification,
            recommendation.code_patch,
            recommendation.risk,
            recommendation.tests_to_run,
        ]
    ).lower()
    bad_tokens = ["</think>", "<tool_call", "analyze_image", "<|", "```tool"]
    return any(token in text for token in bad_tokens)
