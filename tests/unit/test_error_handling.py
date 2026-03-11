import pytest
import time
from medflow.shared.utils.retry import (
    exponential_backoff_retry,
    RetryableError,
)
from medflow.shared.utils.checkpoint import CheckpointManager


def test_retry_success_on_first_attempt():
    """Test successful execution on first attempt."""
    call_count = 0
    
    @exponential_backoff_retry(max_attempts=3)
    def successful_function():
        nonlocal call_count
        call_count += 1
        return "success"
    
    result = successful_function()
    
    assert result == "success"
    assert call_count == 1


def test_retry_success_after_failures():
    """Test successful execution after retries."""
    call_count = 0
    
    @exponential_backoff_retry(max_attempts=3, base_delay=0.1)
    def flaky_function():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise RetryableError("Temporary failure")
        return "success"
    
    result = flaky_function()
    
    assert result == "success"
    assert call_count == 3


def test_retry_exhaustion():
    """Test that retry exhausts after max attempts."""
    call_count = 0
    
    @exponential_backoff_retry(max_attempts=3, base_delay=0.1)
    def always_fails():
        nonlocal call_count
        call_count += 1
        raise RetryableError("Permanent failure")
    
    with pytest.raises(RetryableError):
        always_fails()
    
    assert call_count == 3


def test_exponential_backoff_timing():
    """Test exponential backoff delay calculation."""
    call_times = []
    
    @exponential_backoff_retry(max_attempts=3, base_delay=0.1)
    def timed_function():
        call_times.append(time.time())
        raise RetryableError("Fail")
    
    with pytest.raises(RetryableError):
        timed_function()
    
    assert len(call_times) == 3
    
    delay1 = call_times[1] - call_times[0]
    delay2 = call_times[2] - call_times[1]
    
    assert 0.09 < delay1 < 0.15
    assert 0.18 < delay2 < 0.25


def test_checkpoint_save_and_load():
    """Test checkpoint save and load."""
    manager = CheckpointManager(checkpoint_dir=".test_checkpoints")
    
    agent_state = {"step": 5, "data": "test"}
    partial_results = {"completed": ["task1", "task2"]}
    execution_context = {"start_time": "2024-01-01"}
    
    checkpoint_id = manager.save_checkpoint(
        "test-agent",
        agent_state,
        partial_results,
        execution_context
    )
    
    loaded = manager.load_checkpoint(checkpoint_id)
    
    assert loaded["agent_state"] == agent_state
    assert loaded["partial_results"] == partial_results
    assert loaded["execution_context"] == execution_context


def test_checkpoint_resume():
    """Test resuming from checkpoint."""
    manager = CheckpointManager(checkpoint_dir=".test_checkpoints")
    
    checkpoint_id = manager.save_checkpoint(
        "test-agent",
        {"step": 10},
        {"results": [1, 2, 3]},
        {"context": "test"}
    )
    
    loaded = manager.load_checkpoint(checkpoint_id)
    state, results, context = manager.resume_from_checkpoint(loaded)
    
    assert state == {"step": 10}
    assert results == {"results": [1, 2, 3]}
    assert context == {"context": "test"}


def test_get_latest_checkpoint():
    """Test getting latest checkpoint for agent."""
    manager = CheckpointManager(checkpoint_dir=".test_checkpoints")
    
    manager.save_checkpoint("agent-1", {"step": 1}, {}, {})
    time.sleep(0.1)
    manager.save_checkpoint("agent-1", {"step": 2}, {}, {})
    
    latest = manager.get_latest_checkpoint("agent-1")
    
    assert latest["agent_state"]["step"] == 2


def test_checkpoint_cleanup():
    """Test cleanup of old checkpoints."""
    manager = CheckpointManager(checkpoint_dir=".test_checkpoints")
    
    for i in range(10):
        manager.save_checkpoint(f"agent-cleanup", {"step": i}, {}, {})
        time.sleep(0.01)
    
    manager.cleanup_old_checkpoints("agent-cleanup", keep_last=3)
    
    checkpoints = list(manager.checkpoint_dir.glob("agent-cleanup_*.json"))
    assert len(checkpoints) == 3
