"""
CDP Riva-ASR-Whisper Transcription Service
Uses Cloudera Data Platform with Riva ASR Whisper
"""
import os
import json
import logging
from pathlib import Path
from typing import Dict, Any
import asyncio
import aiohttp
import aiofiles
from config import Config
from services.audio_preprocessor import AudioPreprocessor

logger = logging.getLogger(__name__)

class RivaTranscriptionService:
    """
    Service for transcribing audio using CDP Riva-ASR-Whisper-Large-v3-A10G
    """
    
    def __init__(self):
        # CDP configuration
        self.default_language = Config.DEFAULT_LANGUAGE
        self.cdp_base_url = Config.CDP_BASE_URL
        self.cdp_token = Config.get_cdp_token()
        self.model_name = Config.MODEL_NAME
        
        # Log configuration
        if self.cdp_base_url and self.cdp_token:
            logger.info("Transcription service initialized with CDP")
        else:
            logger.warning("CDP not fully configured - using mock data")
        
    async def check_health(self) -> str:
        """Check if the transcription service is available"""
        try:
            if not self.cdp_base_url or not self.cdp_token:
                return "not_configured"
            return "operational"
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return "error"
    
    async def transcribe(self, audio_file_path: str) -> Dict[str, Any]:
        """
        Transcribe audio file using CDP Riva-ASR with automatic format conversion
        
        Args:
            audio_file_path: Path to the audio file (any format)
            
        Returns:
            Dictionary containing transcription and metadata
            
        Raises:
            Exception: With detailed error message if transcription fails
        """
        # Validate configuration first
        if not self.cdp_base_url:
            raise Exception(
                "❌ CDP Riva ASR endpoint not configured\n\n"
                "Please configure the Riva ASR Whisper endpoint in Settings:\n"
                "Settings → Transcription → Riva ASR Whisper Endpoint URL"
            )
        
        if not self.cdp_token:
            raise Exception(
                "❌ CDP authentication not configured\n\n"
                "Please configure authentication in Settings:\n"
                "Settings → Transcription → CDP Token or CDP JWT Path"
            )
        
        preprocessed_path = None
        is_temp = False
        
        try:
            logger.info(f"Transcribing audio file: {audio_file_path}")
            
            # Get original audio file metadata
            audio_path = Path(audio_file_path)
            original_file_size = audio_path.stat().st_size
            original_format = audio_path.suffix.lstrip('.')
            
            # Step 1: Preprocess audio to Riva-compatible format
            logger.info("Step 1: Preprocessing audio to Riva-compatible format...")
            preprocessed_path, is_temp, duration_seconds = AudioPreprocessor.preprocess_audio(audio_file_path)
            
            # Read preprocessed audio file
            async with aiofiles.open(preprocessed_path, 'rb') as f:
                audio_data = await f.read()
            
            preprocessed_filename = Path(preprocessed_path).name
            
            # Step 2: Transcribe using CDP
            logger.info("Step 2: Sending to Riva ASR for transcription...")
            transcription = await self._transcribe_cdp(audio_data, preprocessed_filename)
            
            result = {
                "text": transcription.get("text", ""),
                "duration": duration_seconds,  # Use actual audio duration
                "confidence": transcription.get("confidence", 0.0),
                "language": transcription.get("language", "en-US"),
                "format": original_format,  # Report original format
                "sample_rate": transcription.get("sample_rate", 16000),
                "metadata": {
                    "file_size": original_file_size,
                    "model": self.model_name,
                    "preprocessed": is_temp,
                }
            }
            
            logger.info(f"Transcription completed. Text length: {len(result['text'])} chars")
            return result
            
        except aiohttp.ClientConnectorError as e:
            error_msg = (
                f"❌ Cannot connect to Riva ASR endpoint\n\n"
                f"Endpoint: {self.cdp_base_url}\n"
                f"Error: Connection refused\n\n"
                f"Please check:\n"
                f"1. CDP endpoint URL is correct in Settings\n"
                f"2. Network connectivity to CDP cluster\n"
                f"3. VPN connection if required\n"
                f"4. Endpoint is deployed and running in CML"
            )
            logger.error(f"Connection error: {str(e)}")
            raise Exception(error_msg)
        
        except asyncio.TimeoutError:
            error_msg = (
                f"❌ Riva ASR request timed out\n\n"
                f"The transcription request took too long (>120s)\n\n"
                f"Please check:\n"
                f"1. CDP endpoint is responsive\n"
                f"2. Audio file size (file: {original_file_size / 1024 / 1024:.1f} MB)\n"
                f"3. Network connection stability"
            )
            logger.error("Timeout error")
            raise Exception(error_msg)
        
        except Exception as e:
            # Check if it's already a formatted error message
            if str(e).startswith("❌"):
                raise
            
            logger.error(f"Unexpected transcription error: {str(e)}")
            raise Exception(
                f"❌ Transcription failed\n\n"
                f"Error: {str(e)}\n\n"
                f"Please check:\n"
                f"1. Audio file format is supported\n"
                f"2. CDP endpoint is configured correctly\n"
                f"3. Authentication token is valid\n"
                f"4. Application logs for detailed error information"
            )
        
        finally:
            # Clean up temporary preprocessed file
            if is_temp and preprocessed_path:
                AudioPreprocessor.cleanup_temp_file(preprocessed_path)
    
    async def _transcribe_cloud(self, audio_data: bytes, filename: str) -> Dict[str, Any]:
        """
        Transcribe using NVIDIA NIM Cloud API
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }
        
        # Prepare multipart form data
        data = aiohttp.FormData()
        data.add_field('file',
                      audio_data,
                      filename=filename,
                      content_type='audio/wav')
        
        url = f"{self.base_url}/audio/transcriptions"
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, data=data) as response:
                if response.status == 200:
                    result = await response.json()
                    return {
                        "text": result.get("text", ""),
                        "duration": result.get("duration", 0),
                        "confidence": result.get("confidence", 0.95),
                        "language": result.get("language", "en-US"),
                    }
                else:
                    error_text = await response.text()
                    logger.error(f"API error {response.status}: {error_text}")
                    raise Exception(f"Transcription API error: {response.status}")
    
    async def _transcribe_cdp(self, audio_data: bytes, filename: str) -> Dict[str, Any]:
        """
        Transcribe using CDP Riva ASR
        Note: Audio is preprocessed to WAV format before calling this method
        """
        # Build correct endpoint URL - ensure it ends with /v1
        base = self.cdp_base_url.rstrip('/')
        if not base.endswith('/v1'):
            base = base + '/v1'
        url = f"{base}/audio/transcriptions"
        
        logger.info(f"Transcribing via CDP: {url}")
        
        headers = {
            "Authorization": f"Bearer {self.cdp_token}"
        }
        
        # Prepare multipart form-data
        # Audio is always WAV (16kHz, mono, 16-bit PCM) after preprocessing
        data = aiohttp.FormData()
        
        data.add_field('file',
                      audio_data,
                      filename=filename,
                      content_type='audio/wav')
        data.add_field('language', self.default_language)
        
        # Timeout: 2 minutes for transcription
        timeout = aiohttp.ClientTimeout(total=120)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers, data=data) as response:
                response_text = await response.text()
                
                if response.status == 200:
                    try:
                        result = json.loads(response_text)
                        logger.info("Transcription successful")
                        return {
                            "text": result.get("text", ""),
                            "duration": result.get("duration", 0),
                            "confidence": result.get("confidence", 0.95),
                            "language": result.get("language", self.default_language),
                            "sample_rate": 16000,
                        }
                    except json.JSONDecodeError as e:
                        logger.error(f"Invalid JSON response: {response_text[:200]}")
                        raise Exception(
                            f"❌ Riva ASR returned invalid response\n\n"
                            f"Response was not valid JSON\n"
                            f"Status: {response.status}\n\n"
                            f"This may indicate an endpoint configuration issue."
                        )
                
                elif response.status == 401:
                    logger.error(f"Authentication failed: {response_text[:200]}")
                    raise Exception(
                        f"❌ Authentication failed with Riva ASR\n\n"
                        f"Status: 401 Unauthorized\n\n"
                        f"Please check:\n"
                        f"1. CDP token is valid and not expired\n"
                        f"2. Token has permissions for Riva ASR endpoint\n"
                        f"3. JWT file at {Config.CDP_JWT_PATH} contains valid token\n\n"
                        f"Update your token in Settings if needed."
                    )
                
                elif response.status == 404:
                    logger.error(f"Endpoint not found: {url}")
                    raise Exception(
                        f"❌ Riva ASR endpoint not found\n\n"
                        f"URL: {url}\n"
                        f"Status: 404 Not Found\n\n"
                        f"Please check:\n"
                        f"1. CDP Base URL is correct\n"
                        f"2. Endpoint path includes '/v1/audio/transcriptions'\n"
                        f"3. Endpoint is deployed in CML\n\n"
                        f"Verify your endpoint URL in Settings."
                    )
                
                elif response.status == 400:
                    logger.error(f"Bad request: {response_text[:500]}")
                    raise Exception(
                        f"❌ Riva ASR rejected the request\n\n"
                        f"Status: 400 Bad Request\n"
                        f"Response: {response_text[:200]}\n\n"
                        f"Possible causes:\n"
                        f"1. Audio file format not supported\n"
                        f"2. File is corrupted\n"
                        f"3. Request format incorrect\n\n"
                        f"Try a different audio file or check file format."
                    )
                
                else:
                    logger.error(f"API error {response.status}: {response_text[:500]}")
                    raise Exception(
                        f"❌ Riva ASR error {response.status}\n\n"
                        f"Response: {response_text[:200]}\n\n"
                        f"Please check the CDP endpoint status in CML dashboard."
                    )
    
    async def _transcribe_local(self, audio_data: bytes, filename: str) -> Dict[str, Any]:
        """
        Transcribe using local NVIDIA NIM deployment
        """
        url = f"{self.local_url}/v1/audio/transcriptions"
        
        data = aiohttp.FormData()
        data.add_field('file',
                      audio_data,
                      filename=filename,
                      content_type='audio/wav')
        data.add_field('language', self.default_language)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data) as response:
                if response.status == 200:
                    result = await response.json()
                    return {
                        "text": result.get("text", ""),
                        "duration": result.get("duration", 0),
                        "confidence": result.get("confidence", 0.95),
                        "language": result.get("language", self.default_language),
                    }
                else:
                    error_text = await response.text()
                    logger.error(f"Local API error {response.status}: {error_text}")
                    raise Exception(f"Local transcription error: {response.status}")
    

