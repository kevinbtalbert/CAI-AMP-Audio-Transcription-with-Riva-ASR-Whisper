"""
Configuration settings for Healthcare Call Analytics
"""
import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Application configuration"""
    
    # CDP (Cloudera Data Platform) Settings - ONLY Deployment Type
    CDP_BASE_URL = os.getenv("CDP_BASE_URL", "")
    CDP_JWT_PATH = os.getenv("CDP_JWT_PATH", "/tmp/jwt")
    CDP_TOKEN = os.getenv("CDP_TOKEN", "")  # Alternative to JWT file
    
    # Nemotron LLM Settings (for enhanced summarization)
    NEMOTRON_ENABLED = os.getenv("NEMOTRON_ENABLED", "true").lower() == "true"
    NEMOTRON_BASE_URL = os.getenv("NEMOTRON_BASE_URL", "")
    NEMOTRON_MODEL_ID = os.getenv("NEMOTRON_MODEL_ID", "nvidia/llama-3.3-nemotron-super-49b-v1")
    
    # Solr Settings (for indexing call analysis data)
    SOLR_ENABLED = os.getenv("SOLR_ENABLED", "false").lower() == "true"
    SOLR_BASE_URL = os.getenv("SOLR_BASE_URL", "")
    SOLR_COLLECTION_NAME = os.getenv("SOLR_COLLECTION_NAME", "healthcare_calls")
    SOLR_TOKEN = os.getenv("SOLR_TOKEN", "")  # Separate CDP token for Solr
    
    # Knox Token Renewal Settings
    AUTO_RENEW_TOKENS = os.getenv("AUTO_RENEW_TOKENS", "true").lower() == "true"
    KNOX_TOKEN_RENEWAL_ENDPOINT = os.getenv("KNOX_TOKEN_RENEWAL_ENDPOINT", "")  # e.g., https://hostname/homepage/knoxtoken/api/v2/token/renew
    KNOX_HADOOP_JWT = os.getenv("KNOX_HADOOP_JWT", "")  # hadoop-jwt cookie for authentication
    
    # Model Configuration
    MODEL_NAME = "nvidia/riva-asr-whisper-large-v3-a10g"
    DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "en")
    
    # Application Settings
    AUDIO_FILES_DIR = os.getenv("AUDIO_FILES_DIR", "audio_files")
    RESULTS_DIR = os.getenv("RESULTS_DIR", "results")
    
    # Server Settings
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8000))
    
    # Supported audio formats
    SUPPORTED_FORMATS = {'.wav', '.mp3', '.m4a', '.flac', '.ogg', '.opus'}
    
    # Maximum file size (100MB)
    MAX_FILE_SIZE = 100 * 1024 * 1024
    
    @classmethod
    def get_cdp_token(cls):
        """Get CDP authentication token from JWT file or environment"""
        if cls.CDP_TOKEN:
            return cls.CDP_TOKEN
        
        try:
            jwt_path = Path(cls.CDP_JWT_PATH)
            if jwt_path.exists():
                with open(jwt_path, 'r') as f:
                    jwt_data = json.load(f)
                    return jwt_data.get("access_token", "")
        except Exception as e:
            print(f"⚠️  Warning: Could not read CDP JWT token: {e}")
        
        return None
    
    @classmethod
    def validate(cls):
        """Validate configuration"""
        token = cls.get_cdp_token()
        
        # Check CDP configuration
        if not token and not cls.CDP_BASE_URL:
            print("⚠️  Warning: CDP_BASE_URL and CDP_TOKEN not set.")
            print("   Using mock transcription data for development.")
            print("   Please configure via Settings UI.")
        elif token and cls.CDP_BASE_URL:
            print("✓ CDP Riva ASR configured")
        elif not token:
            print("⚠️  Warning: No CDP authentication configured (no token or JWT file)")
        elif not cls.CDP_BASE_URL:
            print("⚠️  Warning: CDP_BASE_URL not set")
        
        # Check Nemotron configuration
        if cls.NEMOTRON_ENABLED:
            if cls.NEMOTRON_BASE_URL:
                print("✓ Nemotron LLM enabled for enhanced summarization")
            else:
                print("⚠️  Warning: Nemotron enabled but NEMOTRON_BASE_URL not set")
        else:
            print("ℹ️  Nemotron AI summarization disabled (basic analytics only)")
        
        # Check Solr configuration
        if cls.SOLR_ENABLED:
            if cls.SOLR_BASE_URL:
                print(f"✓ Solr indexing enabled - Collection: {cls.SOLR_COLLECTION_NAME}")
            else:
                print("⚠️  Warning: Solr enabled but SOLR_BASE_URL not set")
        else:
            print("ℹ️  Solr indexing disabled")
        
        # Create directories if they don't exist
        Path(cls.AUDIO_FILES_DIR).mkdir(parents=True, exist_ok=True)
        Path(cls.RESULTS_DIR).mkdir(parents=True, exist_ok=True)
        Path("static").mkdir(parents=True, exist_ok=True)
        
        return True

# Validate configuration on import
Config.validate()

