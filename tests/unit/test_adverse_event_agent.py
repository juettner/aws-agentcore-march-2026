import pytest
from unittest.mock import Mock
from medflow.agents.adverse_event import AdverseEventMonitor
from medflow.shared.models.adverse_event import (
    AdverseEventCheckRequest,
    HistoricalCase,
)


@pytest.fixture
def mock_memory_client():
    client = Mock()
    client.retrieve_similar_cases.return_value = []
    client.store_episode.return_value = True
    return client


@pytest.fixture
def monitor(mock_memory_client):
    return AdverseEventMonitor(memory_client=mock_memory_client)


def test_critical_symptom_severity(monitor):
    """Test severity calculation for critical symptoms."""
    request = AdverseEventCheckRequest(
        patient_id="P001",
        symptoms=["chest pain", "difficulty breathing"],
        medications=["aspirin"],
        timeline="2 hours",
    )

    response = monitor.check_adverse_event(request)

    assert response.severity_grade == 5
    assert response.alert_generated


def test_severe_symptom_severity(monitor):
    """Test severity calculation for severe symptoms."""
    request = AdverseEventCheckRequest(
        patient_id="P002",
        symptoms=["high fever", "severe headache"],
        medications=["ibuprofen"],
        timeline="12 hours",
    )

    response = monitor.check_adverse_event(request)

    assert response.severity_grade == 3
    assert response.alert_generated


def test_mild_symptom_severity(monitor):
    """Test severity calculation for mild symptoms."""
    request = AdverseEventCheckRequest(
        patient_id="P003",
        symptoms=["mild nausea", "fatigue"],
        medications=["vitamin D"],
        timeline="24 hours",
    )

    response = monitor.check_adverse_event(request)

    assert response.severity_grade == 1
    assert not response.alert_generated


def test_pattern_matching_cardiotoxicity(monitor):
    """Test pattern matching for cardiotoxicity."""
    request = AdverseEventCheckRequest(
        patient_id="P004",
        symptoms=["chest pain", "palpitations"],
        medications=["doxorubicin"],
        timeline="1 week",
    )

    response = monitor.check_adverse_event(request)

    assert "cardiotoxicity" in response.matched_patterns


def test_pattern_matching_hepatotoxicity(monitor):
    """Test pattern matching for hepatotoxicity."""
    request = AdverseEventCheckRequest(
        patient_id="P005",
        symptoms=["jaundice", "abdominal pain"],
        medications=["acetaminophen"],
        timeline="3 days",
    )

    response = monitor.check_adverse_event(request)

    assert "hepatotoxicity" in response.matched_patterns


def test_historical_case_influence(mock_memory_client):
    """Test that historical cases influence severity calculation."""
    historical_cases = [
        HistoricalCase(
            case_id="C001",
            patient_profile={"age_range": "40-45"},
            symptoms=["nausea"],
            medications=["drug_x"],
            timeline="24 hours",
            outcome="resolved",
            severity_grade=4,
            similarity_score=0.9,
        ),
        HistoricalCase(
            case_id="C002",
            patient_profile={"age_range": "40-45"},
            symptoms=["nausea"],
            medications=["drug_x"],
            timeline="24 hours",
            outcome="resolved",
            severity_grade=4,
            similarity_score=0.85,
        ),
    ]
    mock_memory_client.retrieve_similar_cases.return_value = historical_cases

    monitor = AdverseEventMonitor(memory_client=mock_memory_client)
    request = AdverseEventCheckRequest(
        patient_id="P006",
        symptoms=["nausea"],
        medications=["drug_x"],
        timeline="24 hours",
    )

    response = monitor.check_adverse_event(request)

    assert response.severity_grade > 1
    assert len(response.historical_cases) == 2


def test_store_outcome(monitor, mock_memory_client):
    """Test storing adverse event outcome."""
    request = AdverseEventCheckRequest(
        patient_id="P007",
        symptoms=["headache"],
        medications=["aspirin"],
        timeline="6 hours",
    )

    result = monitor.store_outcome(request, "resolved", 2)

    assert result is True
    mock_memory_client.store_episode.assert_called_once()


def test_recommendation_urgent(monitor):
    """Test urgent recommendation for grade 4+ events."""
    request = AdverseEventCheckRequest(
        patient_id="P008",
        symptoms=["severe bleeding", "loss of consciousness"],
        medications=["warfarin"],
        timeline="30 minutes",
    )

    response = monitor.check_adverse_event(request)

    assert "URGENT" in response.recommendation
    assert "Immediate" in response.recommendation


def test_recommendation_grade_3(monitor):
    """Test recommendation for grade 3 events."""
    request = AdverseEventCheckRequest(
        patient_id="P009",
        symptoms=["high fever", "confusion"],
        medications=["antibiotic"],
        timeline="8 hours",
    )

    response = monitor.check_adverse_event(request)

    assert "24 hours" in response.recommendation


def test_empty_medications(monitor):
    """Test handling of empty medications list."""
    request = AdverseEventCheckRequest(
        patient_id="P010",
        symptoms=["headache"],
        medications=[],
        timeline="2 hours",
    )

    response = monitor.check_adverse_event(request)

    assert response.severity_grade >= 1
    assert isinstance(response.matched_patterns, list)
