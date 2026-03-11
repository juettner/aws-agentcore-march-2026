import logging
import uuid
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import asyncio

from medflow.shared.models.trial_coordinator import (
    TrialSchedulingRequest,
    TrialSchedulingResponse,
    PatientSchedule,
    TimeSlot,
    A2AMessage,
    MessageType,
    SchedulingProposal,
)

logger = logging.getLogger(__name__)


class SchedulingSubAgent:
    def __init__(self, agent_id: str, patient_id: str, coordinator):
        self.agent_id = agent_id
        self.patient_id = patient_id
        self.coordinator = coordinator
        self.assigned_slots: List[TimeSlot] = []
        self.proposals: List[SchedulingProposal] = []
        
    async def propose_schedule(self, available_slots: List[TimeSlot]):
        """Propose time slots for this patient."""
        proposal = SchedulingProposal(
            proposal_id=str(uuid.uuid4()),
            patient_id=self.patient_id,
            time_slots=available_slots[:3],
            priority=1,
        )
        self.proposals.append(proposal)
        
        await self.coordinator.broadcast_message(
            sender_id=self.agent_id,
            message_type=MessageType.PROPOSAL,
            payload={"proposal": proposal},
        )
        
    async def handle_message(self, message: A2AMessage):
        """Handle incoming A2A messages."""
        if message.message_type == MessageType.PROPOSAL:
            await self._check_conflicts(message.payload["proposal"])
        elif message.message_type == MessageType.CONFLICT:
            await self._negotiate_alternative(message)
        elif message.message_type == MessageType.CONFIRMATION:
            self._confirm_slots(message.payload["slots"])
            
    async def _check_conflicts(self, proposal: SchedulingProposal):
        """Check if proposal conflicts with our slots."""
        for their_slot in proposal.time_slots:
            for our_slot in self.assigned_slots:
                if self._slots_overlap(their_slot, our_slot):
                    await self.coordinator.send_message(
                        sender_id=self.agent_id,
                        recipient_id=proposal.patient_id,
                        message_type=MessageType.CONFLICT,
                        payload={"conflicting_slot": their_slot},
                    )
                    
    def _slots_overlap(self, slot1: TimeSlot, slot2: TimeSlot) -> bool:
        """Check if two time slots overlap."""
        return (slot1.start_time < slot2.end_time and 
                slot1.end_time > slot2.start_time and
                slot1.resource_id == slot2.resource_id)
                
    async def _negotiate_alternative(self, message: A2AMessage):
        """Negotiate alternative time slot."""
        conflicting_slot = message.payload["conflicting_slot"]
        logger.info(f"Agent {self.agent_id} negotiating alternative for conflict")
        
    def _confirm_slots(self, slots: List[TimeSlot]):
        """Confirm assigned time slots."""
        self.assigned_slots = slots


class TrialCoordinatorAgent:
    def __init__(self, max_concurrent_agents: int = 10):
        self.max_concurrent_agents = max_concurrent_agents
        self.active_agents: Dict[str, SchedulingSubAgent] = {}
        self.queued_patients: List[str] = []
        self.message_queue: List[A2AMessage] = []
        self.resource_usage = 0.0
        self.completed_count = 0
        self.in_progress_count = 0
        self.assigned_slots: List[TimeSlot] = []
        self.slot_counter = 0
        
    async def schedule_trial(
        self, request: TrialSchedulingRequest
    ) -> TrialSchedulingResponse:
        """Schedule multiple patients using swarm coordination."""
        start_time = datetime.now()
        schedules: List[PatientSchedule] = []
        conflicts_resolved = 0
        self.assigned_slots = []
        self.slot_counter = 0
        
        for patient_id in request.patient_ids:
            if len(self.active_agents) < self.max_concurrent_agents:
                await self._spawn_sub_agent(patient_id, request)
            else:
                self.queued_patients.append(patient_id)
                
        while self.active_agents or self.queued_patients:
            await asyncio.sleep(0.1)
            
            if self.resource_usage > 0.8:
                self._reduce_concurrency()
                
            completed_agents = [
                agent_id for agent_id, agent in self.active_agents.items()
                if agent.assigned_slots
            ]
            
            for agent_id in completed_agents:
                agent = self.active_agents.pop(agent_id)
                schedules.append(
                    PatientSchedule(
                        patient_id=agent.patient_id,
                        assigned_slots=agent.assigned_slots,
                        status="confirmed",
                    )
                )
                self.completed_count += 1
                self.in_progress_count -= 1
                
                if self.queued_patients:
                    next_patient = self.queued_patients.pop(0)
                    await self._spawn_sub_agent(next_patient, request)
                    
            if not self.active_agents and not self.queued_patients:
                break
                
        conflicts_resolved = self._validate_no_conflicts(schedules)
        
        return TrialSchedulingResponse(
            trial_id=request.trial_id,
            schedules=schedules,
            conflicts_resolved=conflicts_resolved,
            total_messages_exchanged=len(self.message_queue),
            completion_time=datetime.now(),
            resource_usage_peak=self.resource_usage,
        )
        
    async def _spawn_sub_agent(
        self, patient_id: str, request: TrialSchedulingRequest
    ):
        """Spawn a new sub-agent for patient scheduling."""
        agent_id = f"agent-{patient_id}"
        sub_agent = SchedulingSubAgent(agent_id, patient_id, self)
        self.active_agents[agent_id] = sub_agent
        self.in_progress_count += 1
        
        available_slots = self._generate_available_slots(request, patient_id)
        await sub_agent.propose_schedule(available_slots)
        
        assigned_slot = available_slots[0]
        assigned_slot.patient_id = patient_id
        sub_agent.assigned_slots = [assigned_slot]
        self.assigned_slots.append(assigned_slot)
        
    def _generate_available_slots(
        self, request: TrialSchedulingRequest, patient_id: str
    ) -> List[TimeSlot]:
        """Generate non-conflicting available time slots."""
        slots = []
        
        resource_idx = self.slot_counter % len(request.available_resources)
        resource = request.available_resources[resource_idx]
        
        hours_offset = self.slot_counter
        start_time = request.scheduling_window_start + timedelta(hours=hours_offset)
        
        slot = TimeSlot(
            start_time=start_time,
            end_time=start_time + timedelta(hours=1),
            resource_id=resource,
            patient_id=patient_id,
        )
        slots.append(slot)
        
        self.slot_counter += 1
        
        return slots
        
    async def send_message(
        self,
        sender_id: str,
        recipient_id: str,
        message_type: MessageType,
        payload: Dict,
    ):
        """Send A2A message to specific recipient."""
        message = A2AMessage(
            message_id=str(uuid.uuid4()),
            sender_id=sender_id,
            recipient_id=recipient_id,
            message_type=message_type,
            payload=payload,
            timestamp=datetime.now(),
            broadcast=False,
        )
        self.message_queue.append(message)
        
        if recipient_id in self.active_agents:
            await self.active_agents[recipient_id].handle_message(message)
            
    async def broadcast_message(
        self, sender_id: str, message_type: MessageType, payload: Dict
    ):
        """Broadcast A2A message to all swarm agents."""
        message = A2AMessage(
            message_id=str(uuid.uuid4()),
            sender_id=sender_id,
            recipient_id=None,
            message_type=message_type,
            payload=payload,
            timestamp=datetime.now(),
            broadcast=True,
        )
        self.message_queue.append(message)
        
        for agent_id, agent in self.active_agents.items():
            if agent_id != sender_id:
                await agent.handle_message(message)
                
    def _reduce_concurrency(self):
        """Reduce concurrency when resource usage is high."""
        if self.max_concurrent_agents > 1:
            self.max_concurrent_agents -= 1
            logger.warning(
                f"Reducing concurrency to {self.max_concurrent_agents} "
                f"due to high resource usage ({self.resource_usage:.1%})"
            )
            
    def _validate_no_conflicts(self, schedules: List[PatientSchedule]) -> int:
        """Validate that final schedule has no conflicts."""
        conflicts = 0
        all_slots = []
        
        for schedule in schedules:
            all_slots.extend(schedule.assigned_slots)
            
        for i, slot1 in enumerate(all_slots):
            for slot2 in all_slots[i + 1 :]:
                if self._slots_conflict(slot1, slot2):
                    conflicts += 1
                    
        return conflicts
        
    def _slots_conflict(self, slot1: TimeSlot, slot2: TimeSlot) -> bool:
        """Check if two slots conflict."""
        return (slot1.start_time < slot2.end_time and 
                slot1.end_time > slot2.start_time and
                slot1.resource_id == slot2.resource_id)
                
    def get_progress(self) -> Dict[str, int]:
        """Get real-time progress updates."""
        return {
            "completed": self.completed_count,
            "in_progress": self.in_progress_count,
            "queued": len(self.queued_patients),
        }
