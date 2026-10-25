"""
Finite State Machine for Review lifecycle management.

This service class manages state transitions for the Review model,
ensuring that only valid transitions are allowed and preventing
invalid state changes that could corrupt the workflow.
"""

from typing import Protocol

from app.review_state import ReviewState


class StateTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""

    def __init__(
        self,
        current_state: ReviewState,
        target_state: ReviewState,
        message: str | None = None,
    ) -> None:
        self.current_state = current_state
        self.target_state = target_state
        self.message = (
            message
            or f"Invalid transition from {current_state.value} to {target_state.value}"
        )
        super().__init__(self.message)


class ReviewProtocol(Protocol):
    """Protocol for Review model to allow type checking without circular imports."""

    id: str
    state: ReviewState


class ReviewFSM:
    """
    Finite State Machine for Review lifecycle management.

    This class enforces valid state transitions and prevents
    invalid state changes that could corrupt the workflow.

    State transitions:
        NEW -> ANALYZING / IGNORED
        ANALYZING -> AUTO_APPROVED
        ANALYZING -> DRAFT_PENDING
        ANALYZING -> ESCALATED / IGNORED
        DRAFT_PENDING -> APPROVED
        APPROVED / AUTO_APPROVED -> PUBLISHING
        PUBLISHING -> PUBLISHED
        PUBLISHING -> PUBLISH_FAILED
    """

    # Valid transitions mapping: {current_state: [valid_next_states]}
    _VALID_TRANSITIONS: dict[ReviewState, set[ReviewState]] = {
        ReviewState.NEW: {ReviewState.ANALYZING, ReviewState.IGNORED},
        ReviewState.ANALYZING: {
            ReviewState.AUTO_APPROVED,
            ReviewState.DRAFT_PENDING,
            ReviewState.ESCALATED,
            ReviewState.IGNORED,
        },
        ReviewState.DRAFT_PENDING: {ReviewState.APPROVED},
        ReviewState.AUTO_APPROVED: {ReviewState.PUBLISHING},
        ReviewState.APPROVED: {ReviewState.PUBLISHING},
        ReviewState.PUBLISHING: {
            ReviewState.PUBLISHED,
            ReviewState.PUBLISH_FAILED,
        },
        ReviewState.ESCALATED: set(),  # Terminal state
        ReviewState.IGNORED: set(),  # Terminal state
        ReviewState.PUBLISHED: set(),  # Terminal state
        ReviewState.PUBLISH_FAILED: set(),  # Terminal state
    }

    @classmethod
    def _validate_transition(
        cls, current_state: ReviewState, target_state: ReviewState
    ) -> None:
        """
        Validate that a state transition is allowed.

        Args:
            current_state: The current state of the review
            target_state: The desired target state

        Raises:
            StateTransitionError: If the transition is not valid
        """
        valid_next_states = cls._VALID_TRANSITIONS.get(current_state, set())

        if target_state not in valid_next_states:
            raise StateTransitionError(
                current_state=current_state,
                target_state=target_state,
                message=f"Cannot transition from {current_state.value} to {target_state.value}. "
                f"Valid transitions from {current_state.value}: {[s.value for s in valid_next_states]}",
            )

    @classmethod
    def start_analysis(cls, review: ReviewProtocol) -> ReviewState:
        """
        Transition: NEW -> ANALYZING

        Start the SI analysis process for a new review.

        Args:
            review: The review instance to transition

        Returns:
            The new state (ANALYZING)

        Raises:
            StateTransitionError: If current state is not NEW
        """
        if review.state != ReviewState.NEW:
            raise StateTransitionError(
                current_state=review.state,
                target_state=ReviewState.ANALYZING,
                message="Can only start analysis from NEW state",
            )

        review.state = ReviewState.ANALYZING
        return ReviewState.ANALYZING

    @classmethod
    def approve_auto(cls, review: ReviewProtocol) -> ReviewState:
        """
        Transition: ANALYZING -> AUTO_APPROVED

        Auto-approve the review after SI analysis (low risk, positive sentiment).

        Args:
            review: The review instance to transition

        Returns:
            The new state (AUTO_APPROVED)

        Raises:
            StateTransitionError: If current state is not ANALYZING
        """
        cls._validate_transition(review.state, ReviewState.AUTO_APPROVED)

        review.state = ReviewState.AUTO_APPROVED
        return ReviewState.AUTO_APPROVED

    @classmethod
    def require_human_draft(cls, review: ReviewProtocol) -> ReviewState:
        """
        Transition: ANALYZING -> DRAFT_PENDING

        Require human review and draft generation (high risk or negative sentiment).

        Args:
            review: The review instance to transition

        Returns:
            The new state (DRAFT_PENDING)

        Raises:
            StateTransitionError: If current state is not ANALYZING
        """
        cls._validate_transition(review.state, ReviewState.DRAFT_PENDING)

        review.state = ReviewState.DRAFT_PENDING
        return ReviewState.DRAFT_PENDING

    @classmethod
    def escalate_threat(cls, review: ReviewProtocol) -> ReviewState:
        """
        Transition: ANALYZING -> ESCALATED

        Escalate critical threat reviews to management (threat_level = 5).

        Args:
            review: The review instance to transition

        Returns:
            The new state (ESCALATED)

        Raises:
            StateTransitionError: If current state is not ANALYZING
        """
        cls._validate_transition(review.state, ReviewState.ESCALATED)

        review.state = ReviewState.ESCALATED
        return ReviewState.ESCALATED

    @classmethod
    def ignore(cls, review: ReviewProtocol) -> ReviewState:
        """Transition an irrelevant review from NEW or ANALYZING to IGNORED."""
        cls._validate_transition(review.state, ReviewState.IGNORED)
        review.state = ReviewState.IGNORED
        return ReviewState.IGNORED

    @classmethod
    def approve_draft(cls, review: ReviewProtocol) -> ReviewState:
        """
        Transition: DRAFT_PENDING -> APPROVED

        Approve the human-drafted response for publication.

        Args:
            review: The review instance to transition

        Returns:
            The new state (APPROVED)

        Raises:
            StateTransitionError: If current state is not DRAFT_PENDING
        """
        cls._validate_transition(review.state, ReviewState.APPROVED)

        review.state = ReviewState.APPROVED
        return ReviewState.APPROVED

    @classmethod
    def publish(cls, review: ReviewProtocol) -> ReviewState:
        """
        Transition: APPROVED / AUTO_APPROVED -> PUBLISHING

        Initiate the publication process to the external platform.

        Args:
            review: The review instance to transition

        Returns:
            The new state (PUBLISHING)

        Raises:
            StateTransitionError: If current state is not APPROVED or AUTO_APPROVED
        """
        cls._validate_transition(review.state, ReviewState.PUBLISHING)

        review.state = ReviewState.PUBLISHING
        return ReviewState.PUBLISHING

    @classmethod
    def confirm_published(cls, review: ReviewProtocol) -> ReviewState:
        """
        Transition: PUBLISHING -> PUBLISHED

        Confirm successful publication to the external platform.

        Args:
            review: The review instance to transition

        Returns:
            The new state (PUBLISHED)

        Raises:
            StateTransitionError: If current state is not PUBLISHING
        """
        cls._validate_transition(review.state, ReviewState.PUBLISHED)

        review.state = ReviewState.PUBLISHED
        return ReviewState.PUBLISHED

    @classmethod
    def fail_publish(cls, review: ReviewProtocol) -> ReviewState:
        """
        Transition: PUBLISHING -> PUBLISH_FAILED

        Mark publication as failed (API error, rate limit, etc.).

        Args:
            review: The review instance to transition

        Returns:
            The new state (PUBLISH_FAILED)

        Raises:
            StateTransitionError: If current state is not PUBLISHING
        """
        cls._validate_transition(review.state, ReviewState.PUBLISH_FAILED)

        review.state = ReviewState.PUBLISH_FAILED
        return ReviewState.PUBLISH_FAILED

    @classmethod
    def get_valid_transitions(cls, current_state: ReviewState) -> set[ReviewState]:
        """
        Get all valid next states for a given current state.

        Args:
            current_state: The current state

        Returns:
            Set of valid next states
        """
        return cls._VALID_TRANSITIONS.get(current_state, set()).copy()

    @classmethod
    def can_transition(
        cls, current_state: ReviewState, target_state: ReviewState
    ) -> bool:
        """
        Check if a transition is valid without performing it.

        Args:
            current_state: The current state
            target_state: The desired target state

        Returns:
            True if the transition is valid, False otherwise
        """
        valid_next_states = cls._VALID_TRANSITIONS.get(current_state, set())
        return target_state in valid_next_states
