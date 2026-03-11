import logging
from typing import AsyncIterator, Optional
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class NovaSonicClient:
    def __init__(self):
        self.bedrock_runtime = boto3.client("bedrock-runtime")
        self.model_id = "amazon.nova-sonic-v1"
        
    async def speech_to_text_stream(
        self, audio_stream: AsyncIterator[bytes]
    ) -> AsyncIterator[str]:
        """Convert streaming audio to text in real-time."""
        try:
            async for audio_chunk in audio_stream:
                response = self.bedrock_runtime.invoke_model(
                    modelId=self.model_id,
                    body={
                        "inputAudio": audio_chunk,
                        "task": "transcription",
                    },
                )
                
                text = response.get("text", "")
                if text:
                    yield text
                    
        except ClientError as e:
            logger.error(f"Speech-to-text error: {e}")
            raise
    
    async def text_to_speech_stream(
        self, text: str
    ) -> AsyncIterator[bytes]:
        """Convert text to streaming audio in real-time."""
        try:
            response = self.bedrock_runtime.invoke_model_with_response_stream(
                modelId=self.model_id,
                body={
                    "inputText": text,
                    "task": "synthesis",
                    "voiceId": "default",
                },
            )
            
            for event in response.get("body", []):
                audio_chunk = event.get("audioChunk")
                if audio_chunk:
                    yield audio_chunk
                    
        except ClientError as e:
            logger.error(f"Text-to-speech error: {e}")
            raise
    
    def detect_interruption(
        self, audio_level: float, threshold: float = 0.3
    ) -> bool:
        """Detect if patient is interrupting based on audio level."""
        return audio_level > threshold
