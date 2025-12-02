"""
Health Checker Service
Polls model endpoints to verify they are online and operational
"""
import logging
import asyncio
import aiohttp
from typing import Dict, Any
from datetime import datetime
from config import Config

logger = logging.getLogger(__name__)

class HealthChecker:
    """
    Service for checking health of CDP models (Riva ASR and Nemotron)
    """
    
    def __init__(self):
        self.last_riva_check = None
        self.last_nemotron_check = None
        self.riva_status = "unknown"
        self.nemotron_status = "unknown"
        self.riva_error = None
        self.nemotron_error = None
    
    async def check_riva_health(self) -> Dict[str, Any]:
        """
        Check if Riva ASR endpoint is online using /v1/metrics endpoint
        """
        try:
            if not Config.CDP_BASE_URL:
                return {
                    "status": "not_configured",
                    "error": "CDP_BASE_URL not set",
                    "timestamp": datetime.now().isoformat()
                }
            
            token = Config.get_cdp_token()
            if not token:
                return {
                    "status": "not_configured",
                    "error": "No CDP authentication token available",
                    "timestamp": datetime.now().isoformat()
                }
            
            # Use /v1/metrics endpoint for health check (doesn't require auth, returns 200 if service is up)
            url = f"{Config.CDP_BASE_URL.rstrip('/v1')}/v1/metrics"
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "text/plain"
            }
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=headers) as response:
                    timestamp = datetime.now().isoformat()
                    
                    if response.status == 200:
                        self.riva_status = "online"
                        self.riva_error = None
                        self.last_riva_check = timestamp
                        return {
                            "status": "online",
                            "error": None,
                            "timestamp": timestamp
                        }
                    elif response.status == 404:
                        error = "Metrics endpoint not found - check endpoint URL"
                        self.riva_status = "error"
                        self.riva_error = error
                        self.last_riva_check = timestamp
                        return {
                            "status": "error",
                            "error": error,
                            "timestamp": timestamp
                        }
                    else:
                        error_text = await response.text()
                        error = f"Service returned status {response.status}: {error_text[:200]}"
                        self.riva_status = "error"
                        self.riva_error = error
                        self.last_riva_check = timestamp
                        return {
                            "status": "error",
                            "error": error,
                            "timestamp": timestamp
                        }
        
        except aiohttp.ClientConnectorError as e:
            timestamp = datetime.now().isoformat()
            error = f"Cannot connect to Riva ASR endpoint: {str(e)}"
            self.riva_status = "offline"
            self.riva_error = error
            self.last_riva_check = timestamp
            return {
                "status": "offline",
                "error": error,
                "timestamp": timestamp
            }
        
        except asyncio.TimeoutError:
            timestamp = datetime.now().isoformat()
            error = "Riva ASR endpoint timeout (>10s)"
            self.riva_status = "offline"
            self.riva_error = error
            self.last_riva_check = timestamp
            return {
                "status": "offline",
                "error": error,
                "timestamp": timestamp
            }
        
        except Exception as e:
            timestamp = datetime.now().isoformat()
            error = f"Health check error: {str(e)}"
            logger.error(f"Riva health check error: {str(e)}")
            self.riva_status = "error"
            self.riva_error = error
            self.last_riva_check = timestamp
            return {
                "status": "error",
                "error": error,
                "timestamp": timestamp
            }
    
    async def check_nemotron_health(self) -> Dict[str, Any]:
        """
        Check if Nemotron LLM endpoint is online using /v1/metrics endpoint
        """
        try:
            if not Config.NEMOTRON_ENABLED:
                return {
                    "status": "disabled",
                    "error": None,
                    "timestamp": datetime.now().isoformat()
                }
            
            if not Config.NEMOTRON_BASE_URL:
                return {
                    "status": "not_configured",
                    "error": "NEMOTRON_BASE_URL not set",
                    "timestamp": datetime.now().isoformat()
                }
            
            token = Config.get_cdp_token()
            if not token:
                return {
                    "status": "not_configured",
                    "error": "No CDP authentication token available",
                    "timestamp": datetime.now().isoformat()
                }
            
            # Use /v1/metrics endpoint for health check
            url = f"{Config.NEMOTRON_BASE_URL.rstrip('/v1')}/v1/metrics"
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "text/plain"
            }
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=headers) as response:
                    timestamp = datetime.now().isoformat()
                    
                    if response.status == 200:
                        self.nemotron_status = "online"
                        self.nemotron_error = None
                        self.last_nemotron_check = timestamp
                        return {
                            "status": "online",
                            "error": None,
                            "timestamp": timestamp
                        }
                    elif response.status == 404:
                        error = "Metrics endpoint not found - check endpoint URL"
                        self.nemotron_status = "error"
                        self.nemotron_error = error
                        self.last_nemotron_check = timestamp
                        return {
                            "status": "error",
                            "error": error,
                            "timestamp": timestamp
                        }
                    else:
                        error_text = await response.text()
                        error = f"Service returned status {response.status}: {error_text[:200]}"
                        self.nemotron_status = "error"
                        self.nemotron_error = error
                        self.last_nemotron_check = timestamp
                        return {
                            "status": "error",
                            "error": error,
                            "timestamp": timestamp
                        }
        
        except aiohttp.ClientConnectorError as e:
            timestamp = datetime.now().isoformat()
            error = f"Cannot connect to Nemotron endpoint: {str(e)}"
            self.nemotron_status = "offline"
            self.nemotron_error = error
            self.last_nemotron_check = timestamp
            return {
                "status": "offline",
                "error": error,
                "timestamp": timestamp
            }
        
        except asyncio.TimeoutError:
            timestamp = datetime.now().isoformat()
            error = "Nemotron endpoint timeout (>10s)"
            self.nemotron_status = "offline"
            self.nemotron_error = error
            self.last_nemotron_check = timestamp
            return {
                "status": "offline",
                "error": error,
                "timestamp": timestamp
            }
        
        except Exception as e:
            timestamp = datetime.now().isoformat()
            error = f"Health check error: {str(e)}"
            logger.error(f"Nemotron health check error: {str(e)}")
            self.nemotron_status = "error"
            self.nemotron_error = error
            self.last_nemotron_check = timestamp
            return {
                "status": "error",
                "error": error,
                "timestamp": timestamp
            }
    
    async def check_all(self) -> Dict[str, Any]:
        """
        Check health of all services
        """
        riva_health = await self.check_riva_health()
        nemotron_health = await self.check_nemotron_health()
        
        # Determine overall status
        if riva_health["status"] == "online":
            if nemotron_health["status"] in ["online", "disabled"]:
                overall = "online"
            else:
                overall = "degraded"  # Riva works but Nemotron doesn't
        else:
            overall = "offline"  # Riva is critical
        
        return {
            "overall": overall,
            "riva_asr": riva_health,
            "nemotron": nemotron_health,
            "checked_at": datetime.now().isoformat()
        }

