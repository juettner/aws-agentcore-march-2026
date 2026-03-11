"""AgentCore Memory client for adverse event pattern detection.

Uses the Bedrock AgentCore Memory API for storing and retrieving
episodic adverse event data with semantic and summary strategies.
"""

import json
import logging
import os
import uuid
from typing import List, Dict, Optional
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

from medflow.shared.models.adverse_event import AdverseEventEpisode, HistoricalCase

logger = logging.getLogger(__name__)


class MemoryClient:
    """Client for AgentCore Memory - stores and retrieves adverse event episodes."""

    def __init__(
        self,
        memory_id: Optional[str] = None,
        region: Optional[str] = None,
    ):
        self.memory_id = (memory_id
                          or os.getenv("BEDROCK_AGENTCORE_MEMORY_ID")
                          or os.getenv("AGENTCORE_MEMORY_ID", ""))
        self.region = region or os.getenv("AWS_REGION", "us-west-2")

        # Use the AgentCore client for memory operations
        self.client = boto3.client(
            "bedrock-agentcore",
            region_name=self.region,
        )
        self.max_results = 10
        self.min_similarity_score = 0.6

    def store_episode(self, episode: AdverseEventEpisode) -> bool:
        """Store an adverse event episode in AgentCore Memory.

        Args:
            episode: The adverse event episode to store.

        Returns:
            True if stored successfully, False otherwise.
        """
        try:
            episode_text = self._format_episode_for_embedding(episode)
            actor_id = episode.patient_profile.get("patientId", "unknown")
            strategy_id = os.getenv("AGENTCORE_MEMORY_SEMANTIC_STRATEGY_ID", "")

            self.client.batch_create_memory_records(
                memoryId=self.memory_id,
                records=[
                    {
                        "requestIdentifier": str(uuid.uuid4()),
                        "namespaces": ["/adverse_events/"],
                        "content": {"text": episode_text},
                        "timestamp": datetime.utcnow(),
                        **({"memoryStrategyId": strategy_id} if strategy_id else {}),
                    }
                ],
            )

            logger.info(f"Stored episode {episode.episode_id} in memory")
            return True

        except ClientError as e:
            logger.error(f"Failed to store episode: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error storing episode: {e}")
            return False

    def retrieve_similar_cases(
        self, symptoms: List[str], medications: List[str], timeline: str
    ) -> List[HistoricalCase]:
        """Retrieve similar adverse event cases from AgentCore Memory.

        Args:
            symptoms: List of symptom descriptions
            medications: List of medication names
            timeline: Description of the event timeline

        Returns:
            List of HistoricalCase objects ranked by similarity.
        """
        try:
            query_text = self._format_query(symptoms, medications, timeline)
            semantic_strategy_id = os.getenv("AGENTCORE_MEMORY_SEMANTIC_STRATEGY_ID", "")

            search_criteria: dict = {"searchQuery": query_text, "topK": self.max_results}
            if semantic_strategy_id:
                search_criteria["memoryStrategyId"] = semantic_strategy_id

            response = self.client.retrieve_memory_records(
                memoryId=self.memory_id,
                namespace="/adverse_events/",
                searchCriteria=search_criteria,
                maxResults=self.max_results,
            )

            cases = []
            for record in response.get("memoryRecordSummaries", []):
                content = record.get("content", {}).get("text", "")
                score = record.get("score", 0.0)

                if score >= self.min_similarity_score:
                    cases.append(
                        HistoricalCase(
                            case_id=record.get("memoryRecordId", "unknown"),
                            patient_profile={},
                            symptoms=symptoms,
                            medications=medications,
                            timeline=content,
                            outcome="Retrieved from memory",
                            severity_grade=0,
                            similarity_score=score,
                        )
                    )

            logger.info(f"Retrieved {len(cases)} similar cases from memory")
            return cases

        except ClientError as e:
            logger.error(f"Failed to retrieve similar cases: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error retrieving cases: {e}")
            return []

    def get_session_summary(self, actor_id: str, session_id: str) -> Optional[str]:
        """Retrieve a session summary from memory.

        Args:
            actor_id: The actor (patient) ID
            session_id: The session ID

        Returns:
            Summary text or None if not available.
        """
        try:
            response = self.client.retrieve_memory_records(
                memoryId=self.memory_id,
                namespace="/adverse_events/",
                searchCriteria={"searchQuery": f"Summary for {actor_id} session {session_id}", "topK": 1},
                maxResults=1,
            )
            records = response.get("memoryRecordSummaries", [])
            if records:
                return records[0].get("content", {}).get("text")
            return None

        except ClientError as e:
            logger.error(f"Failed to retrieve session summary: {e}")
            return None

    def _format_episode_for_embedding(self, episode: AdverseEventEpisode) -> str:
        """Format episode data as natural language for semantic embedding."""
        return (
            f"Patient profile: {json.dumps(episode.patient_profile)}. "
            f"Symptoms: {', '.join(episode.symptoms)}. "
            f"Medications: {', '.join(episode.medications)}. "
            f"Timeline: {episode.timeline}. "
            f"Outcome: {episode.outcome}. "
            f"Severity: Grade {episode.severity_grade}."
        )

    def _format_query(
        self, symptoms: List[str], medications: List[str], timeline: str
    ) -> str:
        """Format a similarity query."""
        return (
            f"Symptoms: {', '.join(symptoms)}. "
            f"Medications: {', '.join(medications)}. "
            f"Timeline: {timeline}."
        )
