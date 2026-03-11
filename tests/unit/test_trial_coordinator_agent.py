import pytest
from datetime import datetime, timedelta

from medflow.agents.trial_coordinator import TrialCoordinatorAgent
from medflow.shared.models.trial_coordinator import (
    TrialSchedulingRequest,
    TimeSlot,
    MessageType,
)


@pytest.fixture
def coordinator():
    return TrialCoordinatorAgent(max_concurrent_agents=5)


@pytest.fixture
def scheduling_request():
    return TrialSchedulingRequest(
        trial_id="TRIAL-001",
        patient_ids=["P001", "P002", "P003"],
        available_resources=["Room-A", "Room-B", "Room-C"],
        scheduling_window_start=datetime.now(),
        scheduling_window_end=datetime.now() + timedelta(days=7),
    )


@pytest.mark.asyncio
async def test_sub_agent_spawning(coordinator, scheduling_request):
    """Test spawning sub-agents for multiple patients."""
    response = await coordinator.schedule_trial(scheduling_request)
    
    assert response.trial_id == "TRIAL-001"
    assert len(response.schedules) == 3
    assert all(s.patient_id in scheduling_request.patient_ids for s in response.schedules)


@pytest.mark.asyncio
async def test_concurrency_limit_enforcement(coordinator):
    """Test that concurrency limit is enforced."""
    request = TrialSchedulingRequest(
        trial_id="TRIAL-002",
        patient_ids=[f"P{i:03d}" for i in range(10)],
        available_resources=["Room-A", "Room-B"],
        scheduling_window_start=datetime.now(),
        scheduling_window_end=datetime.now() + timedelta(days=7),
    )
    
    response = await coordinator.schedule_trial(request)
    
    assert len(response.schedules) == 10
    assert coordinator.completed_count == 10


@pytest.mark.asyncio
async def test_queuing_when_limit_exceeded(coordinator):
    """Test queuing when concurrency limit is exceeded."""
    coordinator.max_concurrent_agents = 2
    
    request = TrialSchedulingRequest(
        trial_id="TRIAL-003",
        patient_ids=["P001", "P002", "P003", "P004"],
        available_resources=["Room-A"],
        scheduling_window_start=datetime.now(),
        scheduling_window_end=datetime.now() + timedelta(days=7),
    )
    
    response = await coordinator.schedule_trial(request)
    
    assert len(response.schedules) == 4


@pytest.mark.asyncio
async def test_conflict_detection(coordinator, scheduling_request):
    """Test conflict detection in proposed schedules."""
    response = await coordinator.schedule_trial(scheduling_request)
    
    conflicts = coordinator._validate_no_conflicts(response.schedules)
    assert conflicts == 0


@pytest.mark.asyncio
async def test_a2a_message_sending(coordinator):
    """Test A2A message sending between agents."""
    await coordinator.send_message(
        sender_id="agent-1",
        recipient_id="agent-2",
        message_type=MessageType.PROPOSAL,
        payload={"test": "data"},
    )
    
    assert len(coordinator.message_queue) == 1
    message = coordinator.message_queue[0]
    assert message.sender_id == "agent-1"
    assert message.recipient_id == "agent-2"
    assert not message.broadcast


@pytest.mark.asyncio
async def test_a2a_broadcast_messaging(coordinator):
    """Test A2A broadcast messaging to all agents."""
    await coordinator.broadcast_message(
        sender_id="agent-1",
        message_type=MessageType.BROADCAST,
        payload={"announcement": "test"},
    )
    
    assert len(coordinator.message_queue) == 1
    message = coordinator.message_queue[0]
    assert message.broadcast
    assert message.recipient_id is None


@pytest.mark.asyncio
async def test_progress_reporting(coordinator, scheduling_request):
    """Test real-time progress reporting."""
    progress = coordinator.get_progress()
    
    assert "completed" in progress
    assert "in_progress" in progress
    assert "queued" in progress
    assert progress["completed"] == 0


@pytest.mark.asyncio
async def test_final_schedule_consolidation(coordinator, scheduling_request):
    """Test consolidation of all sub-agent results."""
    response = await coordinator.schedule_trial(scheduling_request)
    
    assert len(response.schedules) == len(scheduling_request.patient_ids)
    for schedule in response.schedules:
        assert schedule.status == "confirmed"
        assert len(schedule.assigned_slots) > 0


def test_slot_overlap_detection(coordinator):
    """Test time slot overlap detection."""
    now = datetime.now()
    
    slot1 = TimeSlot(
        start_time=now,
        end_time=now + timedelta(hours=1),
        resource_id="Room-A",
        patient_id="P001",
    )
    
    slot2 = TimeSlot(
        start_time=now + timedelta(minutes=30),
        end_time=now + timedelta(hours=1, minutes=30),
        resource_id="Room-A",
        patient_id="P002",
    )
    
    assert coordinator._slots_conflict(slot1, slot2)


def test_no_overlap_different_resources(coordinator):
    """Test that slots on different resources don't conflict."""
    now = datetime.now()
    
    slot1 = TimeSlot(
        start_time=now,
        end_time=now + timedelta(hours=1),
        resource_id="Room-A",
        patient_id="P001",
    )
    
    slot2 = TimeSlot(
        start_time=now,
        end_time=now + timedelta(hours=1),
        resource_id="Room-B",
        patient_id="P002",
    )
    
    assert not coordinator._slots_conflict(slot1, slot2)
