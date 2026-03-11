"""Bedrock Knowledge Base client for trial protocols and medical literature retrieval."""

import os
import logging
from typing import Any

import boto3

logger = logging.getLogger(__name__)


class KnowledgeBaseClient:
    """Retrieves trial criteria and medical literature from Bedrock Knowledge Base.

    Wraps the Bedrock Agent Runtime retrieve API (RAG) and the model invoke API
    for semantic search via the Strands retrieve tool pattern.
    """

    def __init__(
        self,
        knowledge_base_id: str | None = None,
        region: str | None = None,
        top_k: int = 5,
        similarity_threshold: float = 0.7,
    ):
        self.knowledge_base_id = knowledge_base_id or os.environ.get(
            "BEDROCK_KNOWLEDGE_BASE_ID", "PENDING_DEPLOYMENT"
        )
        self.top_k = top_k
        self.similarity_threshold = similarity_threshold
        self._client = boto3.client(
            "bedrock-agent-runtime",
            region_name=region or os.environ.get("AWS_REGION", "us-west-2"),
        )

    def retrieve_trial_protocol(self, trial_id: str) -> dict[str, Any]:
        """Retrieve trial inclusion/exclusion criteria from the Knowledge Base.

        Args:
            trial_id: Clinical trial identifier.

        Returns:
            Dict with inclusionCriteria and exclusionCriteria lists.
        """
        results = self._retrieve(f"trial protocol criteria for trial {trial_id}")
        return self._parse_trial_protocol(results)

    def retrieve_medical_literature(self, query: str) -> list[dict[str, Any]]:
        """Semantic search for medical literature supporting an eligibility decision.

        Args:
            query: Natural language query describing the criterion or patient condition.

        Returns:
            List of citation dicts with documentId, title, pageNumber, relevanceScore.
        """
        results = self._retrieve(query)
        return [
            {
                "documentId": r["location"].get("s3Location", {}).get("uri", "unknown"),
                "title": r.get("metadata", {}).get("title", "Unknown Document"),
                "pageNumber": r.get("metadata", {}).get("pageNumber"),
                "relevanceScore": r.get("score", 0.0),
            }
            for r in results
            if r.get("score", 0.0) >= self.similarity_threshold
        ]

    def _retrieve(self, query: str) -> list[dict[str, Any]]:
        """Call Bedrock Knowledge Base retrieve API."""
        if not self.knowledge_base_id or self.knowledge_base_id == "PENDING_DEPLOYMENT":
            logger.warning("Knowledge Base not configured — returning empty results")
            return []
        try:
            response = self._client.retrieve(
                knowledgeBaseId=self.knowledge_base_id,
                retrievalQuery={"text": query},
                retrievalConfiguration={
                    "vectorSearchConfiguration": {"numberOfResults": self.top_k}
                },
            )
            return response.get("retrievalResults", [])
        except Exception as e:
            logger.warning(f"Knowledge Base retrieval failed: {e} — returning empty results")
            return []

    def _parse_trial_protocol(self, results: list[dict]) -> dict[str, Any]:
        """Extract structured criteria from raw retrieval results."""
        inclusion: list[dict] = []
        exclusion: list[dict] = []

        for i, r in enumerate(results):
            content = r.get("content", {}).get("text", "")
            criterion = {
                "criterionId": f"C{i + 1:03d}",
                "criterionText": content,
                "category": "medical",
            }
            if "exclusion" in content.lower():
                exclusion.append(criterion)
            else:
                inclusion.append(criterion)

        return {"inclusionCriteria": inclusion, "exclusionCriteria": exclusion}
