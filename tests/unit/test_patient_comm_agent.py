import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime

from medflow.agents.patient_comm import PatientCommunicationAgent
from medflow.shared.models.patient_comm import PatientCheckInRequest


async def async_generator(items):
    for item in items:
        yield item


@pytest.fixture
def mock_nova_client():
    client = Mock()
    client.text_to_speech_stream = Mock(return_value=async_generator([b"audio"]))
    client.detect_interruption = Mock(return_value=False)
    return client


@pytest.fixture
def mock_adverse_event_monitor():
    monitor = Mock()
    return monitor


@pytest.fixture
def agent(mock_nova_client, mock_adverse_event_monitor):
    return PatientCommunicationAgent(
        nova_client=mock_nova_client,
        adverse_event_monitor=mock_adverse_event_monitor,
    )


@pytest.mark.asyncio
async def test_standard_question_flow(agent, mock_nova_client):
    """Test conversation follows standardized question flow."""
    request = PatientCheckInRequest(
        patient_id="P001",
        scheduled_time=datetime.now(),
    )
    
    async def mock_patient_response(*args):
        return "I'm feeling okay"
    
    agent._get_patient_response = mock_patient_response
    
    response = await agent.conduct_check_in(request)
    
    assert response.patient_id == "P001"
    assert len(response.transcript) >= 5
    assert response.conversation_id is not None


@pytest.mark.asyncio
async def test_interruption_handling(agent, mock_nova_client):
    """Test agent stops speaking when patient interrupts."""
    mock_nova_client.detect_interruption.return_value = True
    
    request = PatientCheckInRequest(
        patient_id="P002",
        scheduled_time=datetime.now(),
    )
    
    async def mock_patient_response(*args):
        return "Sorry to interrupt"
    
    agent._get_patient_response = mock_patient_response
    
    response = await agent.conduct_check_in(request)
    
    interrupted_turns = [t for t in response.transcript if t.interrupted]
    assert len(interrupted_turns) > 0


@pytest.mark.asyncio
async def test_escalation_trigger(agent, mock_adverse_event_monitor):
    """Test escalation to Adverse Event Monitor for concerning symptoms."""
    request = PatientCheckInRequest(
        patient_id="P003",
        scheduled_time=datetime.now(),
    )
    
    responses = [
        "I'm okay",
        "I have severe chest pain",
        "Yes, taking medications",
        "No side effects",
        "No concerns",
    ]
    response_iter = iter(responses)
    
    async def mock_patient_response(*args):
        return next(response_iter)
    
    agent._get_patient_response = mock_patient_response
    
    from medflow.shared.models.adverse_event import AdverseEventResponse
    mock_adverse_event_monitor.check_adverse_event.return_value = AdverseEventResponse(
        patient_id="P003",
        severity_grade=5,
        alert_generated=True,
        matched_patterns=[],
        historical_cases=[],
        confidence_score=0.9,
        recommendation="URGENT",
        timestamp=datetime.now(),
    )
    
    response = await agent.conduct_check_in(request)
    
    assert response.escalation_required
    assert "pain" in response.symptoms_reported


@pytest.mark.asyncio
async def test_conversation_summary_generation(agent):
    """Test conversation summary is generated correctly."""
    request = PatientCheckInRequest(
        patient_id="P004",
        scheduled_time=datetime.now(),
    )
    
    responses = [
        "I'm feeling good",
        "No new symptoms",
        "Yes, taking all medications",
        "No side effects",
        "No concerns",
    ]
    response_iter = iter(responses)
    
    async def mock_patient_response(*args):
        return next(response_iter)
    
    agent._get_patient_response = mock_patient_response
    
    response = await agent.conduct_check_in(request)
    
    assert response.summary_generated_at is not None
    assert response.duration_seconds >= 0
    assert response.audio_recording_url.startswith("s3://")


@pytest.mark.asyncio
async def test_patient_hangs_up_immediately(agent):
    """Test edge case: patient hangs up immediately."""
    request = PatientCheckInRequest(
        patient_id="P005",
        scheduled_time=datetime.now(),
    )
    
    async def mock_patient_response(*args):
        return ""
    
    agent._get_patient_response = mock_patient_response
    
    response = await agent.conduct_check_in(request)
    
    assert response.patient_id == "P005"
    assert len(response.symptoms_reported) == 0


@pytest.mark.asyncio
async def test_no_verbal_responses(agent):
    """Test edge case: patient provides no verbal responses."""
    request = PatientCheckInRequest(
        patient_id="P006",
        scheduled_time=datetime.now(),
    )
    
    async def mock_patient_response(*args):
        return "..."
    
    agent._get_patient_response = mock_patient_response
    
    response = await agent.conduct_check_in(request)
    
    assert response.patient_id == "P006"
    assert not response.escalation_required


def test_symptom_extraction(agent):
    """Test symptom extraction from patient response."""
    symptoms = []
    adherence = {}
    concerns = []
    
    agent._extract_information(
        "Have you experienced any new symptoms?",
        "I have a headache and feel nauseous",
        symptoms,
        adherence,
        concerns,
    )
    
    assert "headache" in symptoms
    assert "nausea" in symptoms


def test_medication_adherence_extraction(agent):
    """Test medication adherence extraction."""
    symptoms = []
    adherence = {}
    concerns = []
    
    agent._extract_information(
        "Are you taking your medications as prescribed?",
        "Yes, I'm taking all my medications",
        symptoms,
        adherence,
        concerns,
    )
    
    assert adherence.get("prescribed_medications") is True


def test_escalation_check_with_context(agent):
    """Test escalation check with full_responses context."""
    agent.full_responses = ["I have chest pain"]
    assert agent._check_escalation(["pain"]) is True
    
    agent.full_responses = ["I have difficulty breathing"]
    assert agent._check_escalation([]) is True
    
    agent.full_responses = ["I have a mild headache"]
    assert agent._check_escalation(["headache"]) is False
