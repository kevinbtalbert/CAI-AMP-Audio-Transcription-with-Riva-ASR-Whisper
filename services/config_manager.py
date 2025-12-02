"""
Configuration Manager Service
Handles reading and writing configuration to .env file
"""
import os
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)

class ConfigManager:
    """
    Manages configuration persistence to .env file
    """
    
    def __init__(self, env_file: str = ".env"):
        self.env_file = Path(env_file)
        self.ensure_env_file()
    
    def ensure_env_file(self):
        """Ensure .env file exists"""
        if not self.env_file.exists():
            logger.info(f"Creating {self.env_file}")
            self.env_file.touch()
    
    def read_env(self) -> Dict[str, str]:
        """Read current .env file"""
        env_vars = {}
        
        if not self.env_file.exists():
            return env_vars
        
        with open(self.env_file, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue
                
                # Parse KEY=VALUE
                if '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
        
        return env_vars
    
    def write_env(self, updates: Dict[str, Any]) -> bool:
        """
        Update .env file with new values
        
        Args:
            updates: Dictionary of key-value pairs to update
            
        Returns:
            True if successful
        """
        try:
            # Read existing file
            existing_vars = self.read_env()
            
            # Update with new values
            for key, value in updates.items():
                if value is None:
                    # Remove key if value is None
                    existing_vars.pop(key, None)
                else:
                    # Convert boolean to string
                    if isinstance(value, bool):
                        value = "true" if value else "false"
                    existing_vars[key] = str(value)
            
            # Write back to file with proper formatting
            self._write_formatted_env(existing_vars)
            
            logger.info(f"Configuration saved to {self.env_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error writing .env file: {str(e)}")
            return False
    
    def _write_formatted_env(self, env_vars: Dict[str, str]):
        """Write .env file with nice formatting and sections"""
        
        # Define sections for organization
        sections = {
            "CDP Riva ASR Configuration": ["CDP_BASE_URL", "CDP_JWT_PATH", "CDP_TOKEN"],
            "Nemotron LLM (AI Summarization)": ["NEMOTRON_ENABLED", "NEMOTRON_BASE_URL", "NEMOTRON_MODEL_ID"],
            "Model Settings": ["DEFAULT_LANGUAGE"],
            "Application": ["AUDIO_FILES_DIR", "RESULTS_DIR"],
            "Server": ["HOST", "PORT"],
        }
        
        lines = [
            "# Healthcare Call Analytics - Configuration",
            "# Auto-generated and updated by Settings UI",
            "# Last updated: " + self._get_timestamp(),
            ""
        ]
        
        # Write each section
        for section_name, keys in sections.items():
            # Check if any keys from this section exist
            section_vars = {k: v for k, v in env_vars.items() if k in keys}
            
            if section_vars:
                lines.append(f"# {section_name}")
                lines.append("# " + "=" * 70)
                
                for key in keys:
                    if key in env_vars:
                        value = env_vars[key]
                        lines.append(f"{key}={value}")
                
                lines.append("")
        
        # Write any remaining variables not in sections
        written_keys = set()
        for keys in sections.values():
            written_keys.update(keys)
        
        remaining = {k: v for k, v in env_vars.items() if k not in written_keys}
        if remaining:
            lines.append("# Other Settings")
            lines.append("# " + "=" * 70)
            for key, value in sorted(remaining.items()):
                lines.append(f"{key}={value}")
            lines.append("")
        
        # Write to file
        with open(self.env_file, 'w') as f:
            f.write('\n'.join(lines))
    
    def _get_timestamp(self):
        """Get formatted timestamp"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def update_setting(self, key: str, value: Any) -> bool:
        """
        Update a single setting
        
        Args:
            key: Setting key
            value: Setting value
            
        Returns:
            True if successful
        """
        return self.write_env({key: value})
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        Get a single setting
        
        Args:
            key: Setting key
            default: Default value if not found
            
        Returns:
            Setting value or default
        """
        env_vars = self.read_env()
        return env_vars.get(key, default)
    
    def reload_env(self):
        """
        Reload environment variables from .env file
        Updates os.environ with current values
        """
        env_vars = self.read_env()
        
        for key, value in env_vars.items():
            os.environ[key] = value
        
        logger.info("Environment variables reloaded from .env")

