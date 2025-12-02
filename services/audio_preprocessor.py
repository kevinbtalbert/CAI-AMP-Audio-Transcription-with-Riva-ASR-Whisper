"""
Audio Preprocessor Service
Converts various audio formats to Riva-compatible format using pure Python libraries
"""
import logging
import tempfile
import warnings
from pathlib import Path
from typing import Tuple, Optional
import numpy as np

# Suppress warnings from audio libraries
warnings.filterwarnings('ignore')

try:
    import soundfile as sf
    SOUNDFILE_AVAILABLE = True
except ImportError:
    SOUNDFILE_AVAILABLE = False

try:
    import resampy
    RESAMPY_AVAILABLE = True
except ImportError:
    RESAMPY_AVAILABLE = False

try:
    import audioread
    AUDIOREAD_AVAILABLE = True
except ImportError:
    AUDIOREAD_AVAILABLE = False

logger = logging.getLogger(__name__)

class AudioPreprocessor:
    """
    Preprocesses audio files to ensure compatibility with Riva ASR
    
    Converts any audio format to:
    - Format: WAV (PCM)
    - Sample Rate: 16000 Hz
    - Channels: Mono (1 channel)
    - Bit Depth: 16-bit
    """
    
    TARGET_SAMPLE_RATE = 16000
    TARGET_CHANNELS = 1
    TARGET_FORMAT = "wav"
    
    @staticmethod
    def check_dependencies() -> Tuple[bool, str]:
        """
        Check if required libraries are available
        
        Returns:
            Tuple of (available, message)
        """
        if not SOUNDFILE_AVAILABLE:
            return False, "soundfile library not installed (pip install soundfile)"
        if not RESAMPY_AVAILABLE:
            return False, "resampy library not installed (pip install resampy)"
        return True, "All dependencies available"
    
    @staticmethod
    def needs_preprocessing(file_path: str) -> bool:
        """
        Check if file needs preprocessing
        
        Args:
            file_path: Path to audio file
            
        Returns:
            True if preprocessing needed, False otherwise
        """
        # Always preprocess to ensure correct format
        return True
    
    @staticmethod
    def preprocess_audio(file_path: str) -> Tuple[str, bool, float]:
        """
        Convert audio file to Riva-compatible format using pure Python
        
        Args:
            file_path: Path to source audio file
            
        Returns:
            Tuple of (processed_file_path, is_temporary, duration_seconds)
            - processed_file_path: Path to processed audio file
            - is_temporary: True if a temporary file was created
            - duration_seconds: Duration of audio file in seconds
            
        Raises:
            Exception: If preprocessing fails
        """
        try:
            logger.info(f"Preprocessing audio file: {file_path}")
            
            # Check dependencies
            available, message = AudioPreprocessor.check_dependencies()
            if not available:
                raise Exception(
                    f"❌ Missing audio processing library\n\n"
                    f"{message}\n\n"
                    f"Install required libraries:\n"
                    f"  pip install soundfile resampy\n"
                )
            
            file_ext = Path(file_path).suffix.lower().lstrip('.')
            logger.info(f"Converting {file_ext} file to Riva-compatible WAV")
            
            # Read audio file - try soundfile first, fall back to audioread for MP3
            try:
                if file_ext in ['wav', 'flac', 'ogg']:
                    # Use soundfile for supported formats (faster)
                    audio_data, original_sr = sf.read(file_path, dtype='float32')
                    logger.info(f"Original audio: {original_sr}Hz, shape: {audio_data.shape}")
                    
                elif file_ext in ['mp3', 'm4a', 'mp4', 'aac']:
                    # Use audioread for MP3 and other compressed formats
                    if not AUDIOREAD_AVAILABLE:
                        raise Exception(
                            f"MP3/M4A support requires audioread library\n"
                            f"Install with: pip install audioread"
                        )
                    
                    logger.info(f"Reading {file_ext.upper()} file with audioread...")
                    with audioread.audio_open(file_path) as f:
                        original_sr = f.samplerate
                        channels = f.channels
                        
                        # Read all audio data
                        data_bytes = b''.join(f)
                        
                        # Convert bytes to numpy array
                        # audioread returns raw PCM as bytes, convert to int16 then float32
                        audio_data = np.frombuffer(data_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                        
                        # If stereo, reshape
                        if channels > 1:
                            audio_data = audio_data.reshape(-1, channels)
                        
                        logger.info(f"Original audio: {original_sr}Hz, {channels} channel(s), "
                                   f"samples: {len(audio_data)}")
                else:
                    # Try soundfile as fallback
                    audio_data, original_sr = sf.read(file_path, dtype='float32')
                    logger.info(f"Original audio: {original_sr}Hz, shape: {audio_data.shape}")
                    
            except Exception as e:
                error_msg = str(e)
                if "❌" in error_msg:
                    raise
                raise Exception(
                    f"Failed to read audio file: {str(e)}\n"
                    f"Format: {file_ext.upper()}\n"
                    f"Supported: WAV, FLAC, OGG (native), MP3/M4A (requires audioread)"
                )
            
            # Convert stereo to mono if needed
            if len(audio_data.shape) > 1 and audio_data.shape[1] > 1:
                logger.info(f"Converting from {audio_data.shape[1]} channels to mono")
                audio_data = np.mean(audio_data, axis=1)
            
            # Resample if needed
            if original_sr != AudioPreprocessor.TARGET_SAMPLE_RATE:
                logger.info(f"Resampling from {original_sr}Hz to {AudioPreprocessor.TARGET_SAMPLE_RATE}Hz")
                audio_data = resampy.resample(
                    audio_data,
                    original_sr,
                    AudioPreprocessor.TARGET_SAMPLE_RATE,
                    filter='kaiser_best'
                )
            
            # Create temporary WAV file
            temp_fd, temp_path = tempfile.mkstemp(suffix='.wav', prefix='riva_audio_')
            
            # Calculate duration in seconds
            duration_seconds = len(audio_data) / AudioPreprocessor.TARGET_SAMPLE_RATE
            
            # Write as 16-bit PCM WAV
            sf.write(
                temp_path,
                audio_data,
                AudioPreprocessor.TARGET_SAMPLE_RATE,
                subtype='PCM_16'  # 16-bit PCM
            )
            
            logger.info(f"Preprocessed audio saved to: {temp_path}")
            logger.info(f"Converted to: {AudioPreprocessor.TARGET_SAMPLE_RATE}Hz, "
                       f"mono, WAV format (PCM 16-bit)")
            logger.info(f"Audio duration: {duration_seconds:.2f} seconds")
            
            return temp_path, True, duration_seconds
            
        except Exception as e:
            # Check if it's already a formatted error
            if str(e).startswith("❌"):
                raise
            
            logger.error(f"Audio preprocessing failed: {str(e)}")
            raise Exception(
                f"❌ Failed to preprocess audio file\n\n"
                f"File: {file_path}\n"
                f"Error: {str(e)}\n\n"
                f"Possible causes:\n"
                f"1. Audio file is corrupted\n"
                f"2. Unsupported audio format (try WAV, FLAC, or OGG)\n"
                f"3. Missing Python libraries (soundfile, resampy)\n\n"
                f"Install libraries:\n"
                f"  pip install soundfile resampy\n"
            )
    
    @staticmethod
    def cleanup_temp_file(file_path: str) -> None:
        """
        Remove temporary preprocessed file
        
        Args:
            file_path: Path to temporary file
        """
        try:
            if file_path and Path(file_path).exists():
                Path(file_path).unlink()
                logger.info(f"Cleaned up temporary file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temporary file {file_path}: {str(e)}")

