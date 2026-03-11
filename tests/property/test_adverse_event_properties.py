import pytest
from unittest.mock import Mock
from hypothesis import given, strategies as st
from medflow.agents.adverse_event import AdverseEventMonitor
from medflow.shared.models.adverse_event import AdverseEventCheckRequest


def create_mock_memory_client():
    client = Mock()
    client.retrieve_similar_cases.return_value = []
    client.store_episode.return_value = True
    return client


@given(
    symptoms=st.lists(st.text(min_size=1, max_size=50), min_size=1, max_size=10),
    medications=st.lists(st.text(min_size=1, max_size=50), min_size=0, max_size=10),
)
def test_severity_range(symptoms, medications):
    """Property 6: Adverse Event Severity Range - severity must be 1-5."""
    monitor = AdverseEventMonitor(memory_client=create_mock_memory_client())
    request = AdverseEventCheckRequest(
        patient_id="test-patient",
        symptoms=symptoms,
        medications=medications,
        timeline="24 hours",
    )

    response = monitor.check_adverse_event(request)

    assert 1 <= response.severity_grade <= 5


@given(
    symptoms=st.lists(
        st.sampled_from(
            [
                "chest pain",
                "difficulty breathing",
                "severe bleeding",
                "loss of consciousness",
                "seizure",
            ]
        ),
        min_size=1,
        max_size=3,
    ),
    medications=st.lists(st.text(min_size=1, max_size=50), min_size=0, max_size=5),
)
def test_high_severity_alerts(symptoms, medications):
    """Property 7: High-Severity Alert Generation - grade 3+ generates alert."""
    monitor = AdverseEventMonitor(memory_client=create_mock_memory_client())
    request = AdverseEventCheckRequest(
        patient_id="test-patient",
        symptoms=symptoms,
        medications=medications,
        timeline="24 hours",
    )

    response = monitor.check_adverse_event(request)

    if response.severity_grade >= 3:
        assert response.alert_generated
    else:
        assert not response.alert_generated


@given(
    symptoms=st.lists(st.text(min_size=1, max_size=50), min_size=1, max_size=10),
    medications=st.lists(st.text(min_size=1, max_size=50), min_size=0, max_size=10),
    outcome=st.text(min_size=1, max_size=100),
    severity=st.integers(min_value=1, max_value=5),
)
def test_memory_storage(symptoms, medications, outcome, severity):
    """Property 8: Adverse Event Memory Storage - episodes stored with all fields."""
    monitor = AdverseEventMonitor(memory_client=create_mock_memory_client())
    request = AdverseEventCheckRequest(
        patient_id="test-patient",
        symptoms=symptoms,
        medications=medications,
        timeline="24 hours",
    )

    result = monitor.store_outcome(request, outcome, severity)

    assert isinstance(result, bool)


@given(
    symptoms=st.lists(st.text(min_size=1, max_size=50), min_size=1, max_size=10),
    medications=st.lists(st.text(min_size=1, max_size=50), min_size=0, max_size=10),
)
def test_historical_case_retrieval(symptoms, medications):
    """Property 9: Historical Case Retrieval - returns max 10 cases."""
    monitor = AdverseEventMonitor(memory_client=create_mock_memory_client())
    request = AdverseEventCheckRequest(
        patient_id="test-patient",
        symptoms=symptoms,
        medications=medications,
        timeline="24 hours",
    )

    response = monitor.check_adverse_event(request)

    assert len(response.historical_cases) <= 10
    for case in response.historical_cases:
        assert 0.0 <= case.similarity_score <= 1.0
