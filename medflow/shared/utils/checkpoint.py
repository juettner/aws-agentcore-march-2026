import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class CheckpointManager:
    """Manages agent state checkpoints for recovery."""
    
    def __init__(self, checkpoint_dir: str = ".checkpoints"):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(exist_ok=True)
        self.checkpoint_interval_seconds = 300  # 5 minutes
        
    def save_checkpoint(
        self,
        agent_id: str,
        agent_state: Dict[str, Any],
        partial_results: Dict[str, Any],
        execution_context: Dict[str, Any]
    ) -> str:
        """Save agent checkpoint."""
        checkpoint_id = f"{agent_id}_{datetime.now().isoformat()}"
        checkpoint_path = self.checkpoint_dir / f"{checkpoint_id}.json"
        
        checkpoint_data = {
            "checkpoint_id": checkpoint_id,
            "agent_id": agent_id,
            "timestamp": datetime.now().isoformat(),
            "agent_state": agent_state,
            "partial_results": partial_results,
            "execution_context": execution_context,
        }
        
        with open(checkpoint_path, 'w') as f:
            json.dump(checkpoint_data, f, indent=2, default=str)
        
        logger.info(f"Saved checkpoint {checkpoint_id}")
        return checkpoint_id
    
    def load_checkpoint(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """Load agent checkpoint."""
        checkpoint_path = self.checkpoint_dir / f"{checkpoint_id}.json"
        
        if not checkpoint_path.exists():
            logger.warning(f"Checkpoint {checkpoint_id} not found")
            return None
        
        with open(checkpoint_path, 'r') as f:
            checkpoint_data = json.load(f)
        
        logger.info(f"Loaded checkpoint {checkpoint_id}")
        return checkpoint_data
    
    def get_latest_checkpoint(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get the most recent checkpoint for an agent."""
        checkpoints = list(self.checkpoint_dir.glob(f"{agent_id}_*.json"))
        
        if not checkpoints:
            return None
        
        latest = max(checkpoints, key=lambda p: p.stat().st_mtime)
        
        with open(latest, 'r') as f:
            checkpoint_data = json.load(f)
        
        logger.info(f"Loaded latest checkpoint for {agent_id}")
        return checkpoint_data
    
    def resume_from_checkpoint(
        self, checkpoint_data: Dict[str, Any]
    ) -> tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        """Extract state from checkpoint for resumption."""
        return (
            checkpoint_data["agent_state"],
            checkpoint_data["partial_results"],
            checkpoint_data["execution_context"],
        )
    
    def cleanup_old_checkpoints(self, agent_id: str, keep_last: int = 5):
        """Clean up old checkpoints, keeping only the most recent."""
        checkpoints = sorted(
            self.checkpoint_dir.glob(f"{agent_id}_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        for checkpoint in checkpoints[keep_last:]:
            checkpoint.unlink()
            logger.info(f"Deleted old checkpoint {checkpoint.name}")
