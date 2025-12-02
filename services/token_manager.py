"""
Knox Token Manager Service
Handles automatic token renewal for CDP Knox tokens
"""
import logging
import requests
import urllib3
import json
import time
import threading
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from config import Config

# Disable SSL warnings for CDP environments
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

class TokenManager:
    """
    Service for managing and auto-renewing Knox tokens
    """
    
    def __init__(self):
        self.tokens = {}  # Store token metadata: {service_name: {access_token, token_id, expires, ...}}
        self.renewal_thread = None
        self.running = False
        self.renewal_interval = 3600  # Check every hour
        self.renewal_buffer = 7200  # Renew 2 hours before expiry
        
    def register_token(
        self, 
        service_name: str,
        access_token: str,
        token_id: Optional[str] = None,
        expires_in: Optional[int] = None,
        renewal_endpoint: Optional[str] = None,
        hadoop_jwt: Optional[str] = None
    ):
        """
        Register a token for automatic renewal
        
        Args:
            service_name: Name of the service (e.g., 'solr', 'riva', 'nemotron')
            access_token: The Bearer token
            token_id: Knox token ID (if available)
            expires_in: Token expiration timestamp (milliseconds)
            renewal_endpoint: Knox token renewal endpoint
            hadoop_jwt: hadoop-jwt cookie for authentication (if needed)
        """
        try:
            if expires_in:
                expires_at = datetime.fromtimestamp(expires_in / 1000)
            else:
                # Default: assume 24 hour expiry
                expires_at = datetime.now() + timedelta(hours=24)
            
            self.tokens[service_name] = {
                'access_token': access_token,
                'token_id': token_id,
                'expires_at': expires_at,
                'expires_in': expires_in,
                'renewal_endpoint': renewal_endpoint,
                'hadoop_jwt': hadoop_jwt,
                'last_renewed': datetime.now()
            }
            
            logger.info(f"Token registered for {service_name}, expires at {expires_at}")
            
            # Start renewal thread if not running
            if not self.running:
                self.start_renewal_service()
                
        except Exception as e:
            logger.error(f"Failed to register token for {service_name}: {e}")
    
    def start_renewal_service(self):
        """Start the background token renewal service"""
        if self.running:
            return
        
        self.running = True
        self.renewal_thread = threading.Thread(target=self._renewal_loop, daemon=True)
        self.renewal_thread.start()
        logger.info("Token renewal service started")
    
    def stop_renewal_service(self):
        """Stop the background token renewal service"""
        self.running = False
        if self.renewal_thread:
            self.renewal_thread.join(timeout=5)
        logger.info("Token renewal service stopped")
    
    def _renewal_loop(self):
        """Background loop that checks and renews tokens"""
        while self.running:
            try:
                self._check_and_renew_tokens()
            except Exception as e:
                logger.error(f"Error in token renewal loop: {e}")
            
            # Sleep for renewal interval
            time.sleep(self.renewal_interval)
    
    def _check_and_renew_tokens(self):
        """Check all registered tokens and renew if needed"""
        now = datetime.now()
        
        for service_name, token_info in list(self.tokens.items()):
            try:
                expires_at = token_info['expires_at']
                time_until_expiry = (expires_at - now).total_seconds()
                
                # Renew if within renewal buffer (2 hours before expiry)
                if time_until_expiry < self.renewal_buffer:
                    logger.info(f"Token for {service_name} expires in {time_until_expiry/3600:.1f} hours, renewing...")
                    success = self._renew_token(service_name, token_info)
                    
                    if success:
                        logger.info(f"Successfully renewed token for {service_name}")
                    else:
                        logger.warning(f"Failed to renew token for {service_name}")
                else:
                    logger.debug(f"Token for {service_name} still valid for {time_until_expiry/3600:.1f} hours")
                    
            except Exception as e:
                logger.error(f"Error checking token for {service_name}: {e}")
    
    def _renew_token(self, service_name: str, token_info: Dict[str, Any]) -> bool:
        """
        Renew a specific token using Knox Token API
        
        Args:
            service_name: Name of the service
            token_info: Token information dictionary
            
        Returns:
            True if renewal successful, False otherwise
        """
        renewal_endpoint = token_info.get('renewal_endpoint')
        access_token = token_info.get('access_token')
        hadoop_jwt = token_info.get('hadoop_jwt')
        
        if not renewal_endpoint:
            logger.warning(f"No renewal endpoint configured for {service_name}")
            return False
        
        try:
            headers = {
                'X-XSRF-HEADER': 'valid',
                'Content-Type': 'text/plain'
            }
            
            # Add authentication
            if hadoop_jwt:
                headers['Cookie'] = f'hadoop-jwt={hadoop_jwt}'
            
            # Renew token
            response = requests.post(
                renewal_endpoint,
                data=access_token,
                headers=headers,
                verify=False,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('renewed') == 'true':
                    # Update expiration time
                    new_expires_ms = int(result.get('expires', 0))
                    new_expires_at = datetime.fromtimestamp(new_expires_ms / 1000)
                    
                    self.tokens[service_name]['expires_at'] = new_expires_at
                    self.tokens[service_name]['expires_in'] = new_expires_ms
                    self.tokens[service_name]['last_renewed'] = datetime.now()
                    
                    # Update config with renewed token (token content stays the same)
                    self._update_config_token(service_name, access_token, new_expires_ms)
                    
                    logger.info(f"Token renewed for {service_name}, new expiry: {new_expires_at}")
                    return True
                else:
                    error = result.get('error', 'Unknown error')
                    logger.error(f"Token renewal failed for {service_name}: {error}")
                    return False
            else:
                logger.error(f"Token renewal request failed for {service_name}: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error renewing token for {service_name}: {e}")
            return False
    
    def _update_config_token(self, service_name: str, token: str, expires_in: int):
        """
        Update configuration with renewed token
        
        Args:
            service_name: Name of the service
            token: The renewed token
            expires_in: New expiration timestamp
        """
        # Update in-memory config
        if service_name == 'solr':
            Config.SOLR_TOKEN = token
        elif service_name == 'cdp':
            Config.CDP_TOKEN = token
        
        # Note: We don't persist to .env on auto-renewal to avoid file churn
        # The token content doesn't change, only the expiration is extended
        logger.debug(f"Updated in-memory token for {service_name}")
    
    def get_token_status(self, service_name: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a registered token
        
        Args:
            service_name: Name of the service
            
        Returns:
            Dictionary with token status or None if not registered
        """
        if service_name not in self.tokens:
            return None
        
        token_info = self.tokens[service_name]
        now = datetime.now()
        expires_at = token_info['expires_at']
        
        return {
            'service': service_name,
            'expires_at': expires_at.isoformat(),
            'time_until_expiry_hours': (expires_at - now).total_seconds() / 3600,
            'last_renewed': token_info['last_renewed'].isoformat(),
            'is_expired': now > expires_at
        }
    
    def get_all_token_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all registered tokens"""
        return {
            service: self.get_token_status(service)
            for service in self.tokens.keys()
        }

# Global token manager instance
token_manager = TokenManager()

