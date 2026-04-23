import pytest
from pydantic import ValidationError

from healthflow.models.schemas import FeedbackCreate, AgentFeedbackStats


def test_feedback_create_valid():
    fb = FeedbackCreate(
        output_id="sess-123",
        agent_type="compare",
        accuracy=5,
        clarity=4,
        helpfulness=3,
        comment="Good output",
    )
    assert fb.accuracy == 5
    assert fb.agent_type == "compare"


def test_feedback_create_invalid_rating_too_low():
    with pytest.raises(ValidationError) as exc_info:
        FeedbackCreate(
            output_id="sess-123",
            agent_type="compare",
            accuracy=0,
            clarity=4,
            helpfulness=3,
        )
    assert "greater than or equal to 1" in str(exc_info.value)


def test_feedback_create_invalid_rating_too_high():
    with pytest.raises(ValidationError) as exc_info:
        FeedbackCreate(
            output_id="sess-123",
            agent_type="compare",
            accuracy=6,
            clarity=4,
            helpfulness=3,
        )
    assert "less than or equal to 5" in str(exc_info.value)


def test_feedback_create_invalid_agent_type():
    with pytest.raises(ValidationError) as exc_info:
        FeedbackCreate(
            output_id="sess-123",
            agent_type="invalid_agent",
            accuracy=3,
            clarity=3,
            helpfulness=3,
        )
    assert "agent_type must be one of" in str(exc_info.value)


def test_feedback_create_comment_too_long():
    with pytest.raises(ValidationError):
        FeedbackCreate(
            output_id="sess-123",
            agent_type="compare",
            accuracy=3,
            clarity=3,
            helpfulness=3,
            comment="x" * 2001,
        )


def test_feedback_create_default_comment():
    fb = FeedbackCreate(
        output_id="sess-123",
        agent_type="compare",
        accuracy=3,
        clarity=3,
        helpfulness=3,
    )
    assert fb.comment == ""


def test_agent_feedback_stats():
    stats = AgentFeedbackStats(
        agent_type="compare",
        total_feedback=42,
        avg_accuracy=4.2,
        avg_clarity=3.8,
        avg_helpfulness=4.0,
        combined_avg=4.0,
    )
    assert stats.combined_avg == 4.0
