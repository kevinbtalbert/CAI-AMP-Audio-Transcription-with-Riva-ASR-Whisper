"""
Healthcare Call Analytics Application
Uses NVIDIA NIM Riva-ASR-Whisper for transcription and analysis
"""
import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
import mimetypes

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from services.transcription import RivaTranscriptionService
from services.analytics import HealthcareAnalyticsService
from services.file_manager import FileManager
from services.summarization import NemotronSummarizationService
from services.config_manager import ConfigManager
from services.health_checker import HealthChecker
from services.solr_indexer import SolrIndexer
from services.token_manager import token_manager
from config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Healthcare Call Analytics",
    description="Audio transcription and analytics for patient-provider calls",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
file_manager = FileManager()
transcription_service = RivaTranscriptionService()
summarization_service = NemotronSummarizationService()
# Pass Nemotron client to analytics for AI-powered extraction
analytics_service = HealthcareAnalyticsService(
    nemotron_client=summarization_service.client if summarization_service.enabled else None
)
config_manager = ConfigManager()
health_checker = HealthChecker()
solr_indexer = SolrIndexer()

# Register tokens for auto-renewal if enabled
if Config.AUTO_RENEW_TOKENS and Config.KNOX_TOKEN_RENEWAL_ENDPOINT:
    # Register Solr token
    if Config.SOLR_TOKEN:
        token_manager.register_token(
            service_name='solr',
            access_token=Config.SOLR_TOKEN,
            renewal_endpoint=Config.KNOX_TOKEN_RENEWAL_ENDPOINT,
            hadoop_jwt=Config.KNOX_HADOOP_JWT
        )
        logger.info("Solr token registered for auto-renewal")
    
    # Register CDP token (for Riva/Nemotron)
    cdp_token = Config.get_cdp_token()
    if cdp_token:
        token_manager.register_token(
            service_name='cdp',
            access_token=cdp_token,
            renewal_endpoint=Config.KNOX_TOKEN_RENEWAL_ENDPOINT,
            hadoop_jwt=Config.KNOX_HADOOP_JWT
        )
        logger.info("CDP token registered for auto-renewal")

# Pydantic models
class FileNode(BaseModel):
    name: str
    path: str
    type: str  # 'file' or 'directory'
    size: Optional[int] = None
    modified: Optional[str] = None
    children: Optional[List['FileNode']] = None

class TranscriptionRequest(BaseModel):
    file_path: str

class AnalysisResult(BaseModel):
    file_path: str
    transcription: str
    call_metadata: Dict[str, Any]
    healthcare_insights: Dict[str, Any]
    timestamp: str
    processing_time: float

# Routes
@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main application page"""
    html_path = Path(__file__).parent / "static" / "index.html"
    with open(html_path, 'r') as f:
        return f.read()

@app.get("/api/health")
async def health_check():
    """Health check endpoint - legacy"""
    return {
        "status": "healthy",
        "services": {
            "file_manager": "operational",
            "transcription": await transcription_service.check_health(),
            "analytics": "operational"
        }
    }

@app.get("/api/health/status")
async def get_health_status():
    """
    Get current health status of all CDP models
    """
    try:
        status = await health_checker.check_all()
        return status
    except Exception as e:
        logger.error(f"Health check error: {str(e)}")
        return {
            "overall": "error",
            "riva_asr": {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            },
            "nemotron": {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        }

@app.post("/api/health/refresh")
async def refresh_health():
    """
    Force refresh of health status for all CDP models
    """
    try:
        status = await health_checker.check_all()
        return status
    except Exception as e:
        logger.error(f"Health refresh error: {str(e)}")
        return {
            "overall": "error",
            "riva_asr": {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            },
            "nemotron": {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        }

@app.get("/api/solr/status")
async def get_solr_status():
    """
    Check Solr connection and collection status
    """
    try:
        status = solr_indexer.check_connection()
        return status
    except Exception as e:
        logger.error(f"Solr status check error: {str(e)}")
        return {
            "status": "error",
            "message": f"Error checking Solr: {str(e)}"
        }

@app.get("/api/tokens/status")
async def get_token_status():
    """
    Get status of all registered tokens (expiration, renewal status)
    """
    try:
        status = token_manager.get_all_token_status()
        return {
            "auto_renewal_enabled": Config.AUTO_RENEW_TOKENS,
            "tokens": status
        }
    except Exception as e:
        logger.error(f"Error getting token status: {str(e)}")
        return {
            "error": str(e),
            "auto_renewal_enabled": Config.AUTO_RENEW_TOKENS,
            "tokens": {}
        }

@app.post("/api/solr/push")
async def push_to_solr(request: dict):
    """
    Push analysis result to Solr collection
    
    Request body should be the complete analysis result JSON
    """
    try:
        if not Config.SOLR_ENABLED:
            raise HTTPException(
                status_code=400, 
                detail="Solr is not enabled. Please enable and configure Solr in Settings."
            )
        
        logger.info(f"Pushing document to Solr: {request.get('file_path', 'unknown')}")
        result = solr_indexer.index_document(request)
        
        if result["success"]:
            logger.info(f"Successfully indexed to Solr: {result.get('document_id')}")
            return result
        else:
            raise HTTPException(status_code=500, detail=result["message"])
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error pushing to Solr: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to push to Solr: {str(e)}")

@app.get("/api/solr/query")
async def query_solr(
    q: str = "*:*",
    rows: int = 20,
    start: int = 0,
    sort: str = "timestamp desc"
):
    """
    Query Solr collection for call analysis data
    """
    try:
        if not Config.SOLR_ENABLED:
            raise HTTPException(
                status_code=400,
                detail="Solr is not enabled. Please enable and configure Solr in Settings."
            )
        
        result = solr_indexer.query_documents(query=q, rows=rows, start=start, sort=sort)
        
        if result["success"]:
            return result
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Query failed"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying Solr: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to query Solr: {str(e)}")

@app.get("/api/solr/facets/{field}")
async def get_facets(field: str, limit: int = 20):
    """
    Get facet counts for a specific field
    """
    try:
        if not Config.SOLR_ENABLED:
            raise HTTPException(
                status_code=400,
                detail="Solr is not enabled. Please enable and configure Solr in Settings."
            )
        
        # Handle special categorical facets (medications, conditions, symptoms)
        if field in ['medications', 'conditions', 'symptoms']:
            result = solr_indexer.get_categorical_facets(field, limit=limit)
        else:
            result = solr_indexer.facet_query(facet_field=field, limit=limit)
        
        if result["success"]:
            return result
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Facet query failed"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting facets: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get facets: {str(e)}")

@app.get("/api/solr/stats")
async def get_solr_stats():
    """
    Get aggregated statistics from Solr collection
    """
    try:
        if not Config.SOLR_ENABLED:
            raise HTTPException(
                status_code=400,
                detail="Solr is not enabled. Please enable and configure Solr in Settings."
            )
        
        # Get total count
        total_result = solr_indexer.query_documents(query="*:*", rows=0)
        
        # Get facets for common fields
        urgency_facets = solr_indexer.facet_query("healthcare_insights.urgency_level.level")
        call_type_facets = solr_indexer.facet_query("healthcare_insights.call_type")
        sentiment_facets = solr_indexer.facet_query("healthcare_insights.sentiment_analysis.overall_sentiment")
        
        return {
            "total_calls": total_result.get("numFound", 0),
            "urgency_distribution": urgency_facets.get("facets", {}),
            "call_type_distribution": call_type_facets.get("facets", {}),
            "sentiment_distribution": sentiment_facets.get("facets", {})
        }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting Solr stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")

@app.get("/api/solr/categorical-facets/{category}")
async def get_categorical_facets(category: str, limit: int = 10):
    """
    Get aggregated facet counts for categorical fields (medications, conditions, symptoms)
    """
    try:
        if not Config.SOLR_ENABLED:
            raise HTTPException(
                status_code=400,
                detail="Solr is not enabled. Please enable and configure Solr in Settings."
            )
        
        if category not in ["medications", "conditions", "symptoms"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid category. Must be one of: medications, conditions, symptoms"
            )
        
        result = solr_indexer.get_categorical_facets(category, limit)
        return result
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting categorical facets for {category}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get {category} facets: {str(e)}")

@app.get("/api/files/browse")
async def browse_files(path: str = ""):
    """
    Browse files in the audio directory with nested folder structure
    """
    try:
        file_tree = file_manager.get_file_tree(path)
        return JSONResponse(content=file_tree)
    except Exception as e:
        logger.error(f"Error browsing files: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/files/upload")
async def upload_file(
    file: UploadFile = File(...),
    folder_path: str = ""
):
    """
    Upload an audio file to the specified folder
    """
    try:
        # Validate file type
        allowed_extensions = {'.wav', '.mp3', '.m4a', '.flac', '.ogg', '.opus'}
        file_ext = Path(file.filename).suffix.lower()
        
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
            )
        
        # Save file
        saved_path = await file_manager.save_uploaded_file(file, folder_path)
        
        return {
            "message": "File uploaded successfully",
            "path": saved_path,
            "filename": file.filename
        }
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/files/{file_path:path}")
async def delete_file(file_path: str):
    """
    Delete an audio file
    """
    try:
        success = file_manager.delete_file(file_path)
        if success:
            return {
                "message": "File deleted successfully",
                "path": file_path
            }
        else:
            raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        logger.error(f"Error deleting file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/files/create-folder")
async def create_folder(path: str, name: str):
    """
    Create a new folder in the audio directory
    """
    try:
        folder_path = file_manager.create_folder(path, name)
        return {
            "message": "Folder created successfully",
            "path": folder_path
        }
    except Exception as e:
        logger.error(f"Error creating folder: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/analyze")
async def analyze_call(request: TranscriptionRequest, background_tasks: BackgroundTasks):
    """
    Analyze a healthcare call:
    0. Check model health before proceeding
    1. Transcribe audio using CDP Riva-ASR
    2. Extract healthcare insights
    3. Generate enhanced summary with Nemotron (if enabled)
    4. Return structured data (ready for Solr)
    """
    try:
        start_time = datetime.now()
        
        # Step 0: Check model health before proceeding
        logger.info("Checking model health before analysis...")
        health_status = await health_checker.check_all()
        
        if health_status['riva_asr']['status'] != 'online':
            error_detail = {
                "error": "Riva ASR is not available",
                "status": health_status['riva_asr']['status'],
                "message": health_status['riva_asr'].get('error', 'Service is offline'),
                "checked_at": health_status['riva_asr'].get('timestamp')
            }
            logger.error(f"Cannot analyze - Riva ASR not online: {error_detail}")
            raise HTTPException(
                status_code=503,
                detail=error_detail
            )
        
        # Warn if Nemotron is down but continue (it's optional)
        if (Config.NEMOTRON_ENABLED and 
            health_status['nemotron']['status'] != 'online'):
            logger.warning(
                f"Nemotron unavailable ({health_status['nemotron']['status']}) - "
                "will skip AI-enhanced summaries"
            )
        
        # Verify file exists
        full_path = file_manager.get_full_path(request.file_path)
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        logger.info(f"Starting analysis for: {request.file_path}")
        
        # Step 1: Transcribe audio using Riva-ASR
        transcription_result = await transcription_service.transcribe(str(full_path))
        
        # Step 2: Extract healthcare insights
        insights = await analytics_service.analyze_healthcare_call(
            transcription=transcription_result['text'],
            metadata=transcription_result.get('metadata', {})
        )
        
        # Step 2.5: Generate enhanced summary with Nemotron if enabled
        if Config.NEMOTRON_ENABLED:
            try:
                enhanced_summary = await summarization_service.generate_enhanced_summary(
                    transcription=transcription_result['text'],
                    healthcare_insights=insights
                )
                insights['enhanced_summary'] = enhanced_summary
                logger.info("Enhanced summary generated with Nemotron")
            except Exception as e:
                logger.warning(f"Could not generate enhanced summary: {str(e)}")
        
        # Step 3: Build structured result
        processing_time = (datetime.now() - start_time).total_seconds()
        
        result = AnalysisResult(
            file_path=request.file_path,
            transcription=transcription_result['text'],
            call_metadata={
                "duration_seconds": transcription_result.get('duration', 0),
                "audio_format": transcription_result.get('format', 'unknown'),
                "sample_rate": transcription_result.get('sample_rate', 0),
                "confidence_score": transcription_result.get('confidence', 0.0),
                "language": transcription_result.get('language', 'en-US'),
            },
            healthcare_insights=insights,
            timestamp=datetime.now().isoformat(),
            processing_time=processing_time
        )
        
        # Save result for future Solr indexing
        await file_manager.save_analysis_result(request.file_path, result.dict())
        
        logger.info(f"Analysis completed in {processing_time:.2f}s")
        
        return result
        
    except Exception as e:
        logger.error(f"Error analyzing call: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/results")
async def get_results(limit: int = 50):
    """
    Get recent analysis results
    """
    try:
        results = file_manager.get_recent_results(limit)
        return {"results": results}
    except Exception as e:
        logger.error(f"Error retrieving results: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/result/{file_path:path}")
async def get_result(file_path: str):
    """
    Get analysis result for a specific file (most recent version)
    """
    try:
        result = file_manager.get_analysis_result(file_path)
        if not result:
            raise HTTPException(status_code=404, detail="Result not found")
        return result
    except Exception as e:
        logger.error(f"Error retrieving result: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/result/{file_path:path}/versions")
async def get_result_versions(file_path: str):
    """
    Get all analysis versions for a file
    """
    try:
        versions = file_manager.get_all_versions(file_path)
        return {"versions": versions, "count": len(versions)}
    except Exception as e:
        logger.error(f"Error retrieving versions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/result/{file_path:path}/version/{version}")
async def get_specific_version(file_path: str, version: int):
    """
    Get specific version of analysis result
    """
    try:
        result = file_manager.get_analysis_result_by_version(file_path, version)
        if not result:
            raise HTTPException(status_code=404, detail=f"Version {version} not found")
        return result
    except Exception as e:
        logger.error(f"Error retrieving version: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/setup-check")
async def check_setup():
    """
    Check if application needs initial setup
    """
    # Check if critical configuration is present
    needs_setup = False
    missing_items = []
    
    # Check CDP configuration
    if not Config.CDP_BASE_URL or Config.CDP_BASE_URL == "":
        needs_setup = True
        missing_items.append("CDP Base URL")
    
    # Check if we have a way to authenticate
    token = Config.get_cdp_token()
    if not token:
        needs_setup = True
        missing_items.append("CDP Token or JWT Path")
    
    return {
        "needs_setup": needs_setup,
        "missing_items": missing_items,
        "is_configured": not needs_setup,
        "message": "Please configure the application in Settings" if needs_setup else "Application is configured"
    }

@app.get("/api/settings")
async def get_settings():
    """
    Get current configuration settings
    """
    # Get current CDP token status (but don't expose the actual token)
    token = Config.get_cdp_token()
    has_token = bool(token)
    token_preview = None
    if token:
        # Show first/last 4 chars for verification
        token_preview = f"{token[:4]}...{token[-4:]}" if len(token) > 8 else "****"
    
    # Get Solr token status
    solr_token = Config.SOLR_TOKEN
    has_solr_token = bool(solr_token)
    solr_token_preview = None
    if solr_token:
        solr_token_preview = f"{solr_token[:4]}...{solr_token[-4:]}" if len(solr_token) > 8 else "****"
    
    return {
        "cdp_base_url": Config.CDP_BASE_URL,
        "cdp_jwt_path": Config.CDP_JWT_PATH,
        "cdp_token_configured": has_token,
        "cdp_token_preview": token_preview,
        "nemotron_enabled": Config.NEMOTRON_ENABLED,
        "nemotron_base_url": Config.NEMOTRON_BASE_URL,
        "nemotron_model_id": Config.NEMOTRON_MODEL_ID,
        "solr_enabled": Config.SOLR_ENABLED,
        "solr_base_url": Config.SOLR_BASE_URL,
        "solr_collection_name": Config.SOLR_COLLECTION_NAME,
        "solr_token_configured": has_solr_token,
        "solr_token_preview": solr_token_preview,
        "auto_renew_tokens": Config.AUTO_RENEW_TOKENS,
        "knox_renewal_endpoint": Config.KNOX_TOKEN_RENEWAL_ENDPOINT,
        "hadoop_jwt_configured": bool(Config.KNOX_HADOOP_JWT),
        "default_language": Config.DEFAULT_LANGUAGE,
        "host": Config.HOST,
        "port": Config.PORT,
    }

@app.post("/api/settings")
async def update_settings(settings: Dict[str, Any]):
    """
    Update configuration settings and persist to .env file
    """
    try:
        # Prepare settings for .env file
        env_updates = {}
        
        # CDP Configuration
        if "cdp_base_url" in settings:
            Config.CDP_BASE_URL = settings["cdp_base_url"]
            env_updates["CDP_BASE_URL"] = settings["cdp_base_url"]
        
        if "cdp_jwt_path" in settings:
            Config.CDP_JWT_PATH = settings["cdp_jwt_path"]
            env_updates["CDP_JWT_PATH"] = settings["cdp_jwt_path"]
        
        # Handle CDP Token (if provided)
        if "cdp_token" in settings and settings["cdp_token"]:
            token = settings["cdp_token"].strip()
            if token:
                Config.CDP_TOKEN = token
                env_updates["CDP_TOKEN"] = token
                logger.info("CDP Token updated from UI")
        
        if "nemotron_enabled" in settings:
            Config.NEMOTRON_ENABLED = settings["nemotron_enabled"]
            env_updates["NEMOTRON_ENABLED"] = "true" if settings["nemotron_enabled"] else "false"
        
        if "nemotron_base_url" in settings:
            Config.NEMOTRON_BASE_URL = settings["nemotron_base_url"]
            env_updates["NEMOTRON_BASE_URL"] = settings["nemotron_base_url"]
        
        if "nemotron_model_id" in settings:
            Config.NEMOTRON_MODEL_ID = settings["nemotron_model_id"]
            env_updates["NEMOTRON_MODEL_ID"] = settings["nemotron_model_id"]
        
        # Solr Configuration
        if "solr_enabled" in settings:
            Config.SOLR_ENABLED = settings["solr_enabled"]
            env_updates["SOLR_ENABLED"] = "true" if settings["solr_enabled"] else "false"
        
        if "solr_base_url" in settings:
            Config.SOLR_BASE_URL = settings["solr_base_url"]
            env_updates["SOLR_BASE_URL"] = settings["solr_base_url"]
        
        if "solr_collection_name" in settings:
            Config.SOLR_COLLECTION_NAME = settings["solr_collection_name"]
            env_updates["SOLR_COLLECTION_NAME"] = settings["solr_collection_name"]
        
        # Handle Solr Token (if provided)
        if "solr_token" in settings and settings["solr_token"]:
            token = settings["solr_token"].strip()
            if token:
                Config.SOLR_TOKEN = token
                env_updates["SOLR_TOKEN"] = token
                logger.info("Solr Token updated from UI")
        
        # Knox Token Renewal Settings
        if "auto_renew_tokens" in settings:
            Config.AUTO_RENEW_TOKENS = settings["auto_renew_tokens"]
            env_updates["AUTO_RENEW_TOKENS"] = "true" if settings["auto_renew_tokens"] else "false"
        
        if "knox_renewal_endpoint" in settings:
            Config.KNOX_TOKEN_RENEWAL_ENDPOINT = settings["knox_renewal_endpoint"]
            env_updates["KNOX_TOKEN_RENEWAL_ENDPOINT"] = settings["knox_renewal_endpoint"]
        
        # Handle hadoop-jwt (if provided)
        if "hadoop_jwt" in settings and settings["hadoop_jwt"]:
            jwt = settings["hadoop_jwt"].strip()
            if jwt:
                Config.KNOX_HADOOP_JWT = jwt
                env_updates["KNOX_HADOOP_JWT"] = jwt
                logger.info("Hadoop JWT updated from UI")
        
        if "default_language" in settings:
            Config.DEFAULT_LANGUAGE = settings["default_language"]
            env_updates["DEFAULT_LANGUAGE"] = settings["default_language"]
        
        # Persist to .env file
        if env_updates:
            success = config_manager.write_env(env_updates)
            if not success:
                raise Exception("Failed to persist settings to .env file")
        
        # Reinitialize services with new config
        global transcription_service, summarization_service, analytics_service, solr_indexer
        transcription_service = RivaTranscriptionService()
        summarization_service = NemotronSummarizationService()
        # Re-initialize analytics with updated Nemotron client
        analytics_service = HealthcareAnalyticsService(
            nemotron_client=summarization_service.client if summarization_service.enabled else None
        )
        # Re-initialize Solr indexer
        solr_indexer = SolrIndexer()
        
        # Re-register tokens for auto-renewal if enabled
        if Config.AUTO_RENEW_TOKENS and Config.KNOX_TOKEN_RENEWAL_ENDPOINT:
            if Config.SOLR_TOKEN:
                token_manager.register_token(
                    service_name='solr',
                    access_token=Config.SOLR_TOKEN,
                    renewal_endpoint=Config.KNOX_TOKEN_RENEWAL_ENDPOINT,
                    hadoop_jwt=Config.KNOX_HADOOP_JWT
                )
            cdp_token = Config.get_cdp_token()
            if cdp_token:
                token_manager.register_token(
                    service_name='cdp',
                    access_token=cdp_token,
                    renewal_endpoint=Config.KNOX_TOKEN_RENEWAL_ENDPOINT,
                    hadoop_jwt=Config.KNOX_HADOOP_JWT
                )
        
        logger.info("Settings updated and persisted successfully")
        return {
            "message": "Settings saved successfully and will persist across restarts",
            "persisted": True,
            "settings": settings
        }
    
    except Exception as e:
        logger.error(f"Error updating settings: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    # Create necessary directories
    os.makedirs("audio_files", exist_ok=True)
    os.makedirs("results", exist_ok=True)
    os.makedirs("static", exist_ok=True)
    
    # Run the application
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

