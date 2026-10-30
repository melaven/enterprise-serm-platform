from app.domain.reviews.fsm import ReviewFSM
from app.infrastructure.persistence.models.review import Review, ReviewState


def test_ignored_state_is_available_and_terminal() -> None:
    review = Review(
        original_text="Irrelevant review",
        draft_response="",
        state=ReviewState.NEW,
    )

    assert review.text == "Irrelevant review"
    assert review.suggested_reply == ""
    assert "updated_at" in Review.__table__.c
    assert ReviewFSM.can_transition(ReviewState.NEW, ReviewState.IGNORED)
    assert ReviewFSM.can_transition(ReviewState.ANALYZING, ReviewState.IGNORED)
    assert ReviewFSM.ignore(review) is ReviewState.IGNORED
    assert review.state is ReviewState.IGNORED
    assert ReviewFSM.get_valid_transitions(ReviewState.IGNORED) == set()
