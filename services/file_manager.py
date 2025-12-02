"""
File Manager Service
Handles file system operations for audio files and analysis results
"""
import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import aiofiles
from fastapi import UploadFile

logger = logging.getLogger(__name__)

class FileManager:
    """
    Manages audio files and analysis results on local filesystem
    """
    
    def __init__(self, base_dir: str = "audio_files", results_dir: str = "results"):
        self.base_dir = Path(base_dir)
        self.results_dir = Path(results_dir)
        
        # Create directories if they don't exist
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"FileManager initialized: {self.base_dir.absolute()}")
    
    def get_file_tree(self, relative_path: str = "") -> Dict[str, Any]:
        """
        Get hierarchical file tree structure
        
        Args:
            relative_path: Path relative to base_dir
            
        Returns:
            Nested dictionary representing file tree
        """
        try:
            target_path = self.base_dir / relative_path
            
            if not target_path.exists():
                return {"error": "Path does not exist"}
            
            if target_path.is_file():
                return self._get_file_info(target_path, relative_path)
            
            # It's a directory - build tree
            items = []
            
            for item in sorted(target_path.iterdir()):
                if item.name.startswith('.'):
                    continue  # Skip hidden files
                
                item_rel_path = str(item.relative_to(self.base_dir))
                
                if item.is_dir():
                    items.append({
                        "name": item.name,
                        "path": item_rel_path,
                        "type": "directory",
                        "modified": datetime.fromtimestamp(item.stat().st_mtime).isoformat(),
                        "has_children": any(item.iterdir())
                    })
                else:
                    # Only include audio files
                    if item.suffix.lower() in ['.wav', '.mp3', '.m4a', '.flac', '.ogg', '.opus']:
                        items.append(self._get_file_info(item, item_rel_path))
            
            return {
                "name": target_path.name or "root",
                "path": relative_path,
                "type": "directory",
                "items": items
            }
            
        except Exception as e:
            logger.error(f"Error building file tree: {str(e)}")
            raise
    
    def _get_file_info(self, file_path: Path, relative_path: str) -> Dict[str, Any]:
        """Get information about a single file"""
        stat = file_path.stat()
        
        return {
            "name": file_path.name,
            "path": relative_path,
            "type": "file",
            "size": stat.st_size,
            "size_formatted": self._format_size(stat.st_size),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "extension": file_path.suffix.lower()
        }
    
    def _format_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"
    
    async def save_uploaded_file(
        self, 
        file: UploadFile, 
        folder_path: str = ""
    ) -> str:
        """
        Save an uploaded file to the audio directory
        
        Args:
            file: UploadFile object from FastAPI
            folder_path: Subfolder path relative to base_dir
            
        Returns:
            Relative path to saved file
        """
        try:
            # Create target directory
            target_dir = self.base_dir / folder_path
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate unique filename if file already exists
            file_path = target_dir / file.filename
            if file_path.exists():
                stem = file_path.stem
                suffix = file_path.suffix
                counter = 1
                while file_path.exists():
                    file_path = target_dir / f"{stem}_{counter}{suffix}"
                    counter += 1
            
            # Save file
            async with aiofiles.open(file_path, 'wb') as f:
                content = await file.read()
                await f.write(content)
            
            relative_path = str(file_path.relative_to(self.base_dir))
            logger.info(f"File saved: {relative_path}")
            
            return relative_path
            
        except Exception as e:
            logger.error(f"Error saving file: {str(e)}")
            raise
    
    def create_folder(self, parent_path: str, folder_name: str) -> str:
        """
        Create a new folder in the audio directory
        
        Args:
            parent_path: Parent folder path relative to base_dir
            folder_name: Name of new folder
            
        Returns:
            Relative path to created folder
        """
        try:
            folder_path = self.base_dir / parent_path / folder_name
            folder_path.mkdir(parents=True, exist_ok=True)
            
            relative_path = str(folder_path.relative_to(self.base_dir))
            logger.info(f"Folder created: {relative_path}")
            
            return relative_path
            
        except Exception as e:
            logger.error(f"Error creating folder: {str(e)}")
            raise
    
    def get_full_path(self, relative_path: str) -> Path:
        """
        Get full filesystem path from relative path
        
        Args:
            relative_path: Path relative to base_dir
            
        Returns:
            Full Path object
        """
        return self.base_dir / relative_path
    
    def delete_file(self, relative_path: str) -> bool:
        """
        Delete a file from the audio directory
        
        Args:
            relative_path: Path to file relative to base_dir
            
        Returns:
            True if deleted successfully, False if file not found
        """
        try:
            full_path = self.base_dir / relative_path
            
            if not full_path.exists():
                logger.warning(f"File not found for deletion: {relative_path}")
                return False
            
            if not full_path.is_file():
                logger.error(f"Cannot delete - not a file: {relative_path}")
                raise Exception("Cannot delete directories, only files")
            
            # Delete the file
            full_path.unlink()
            logger.info(f"File deleted: {relative_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting file: {str(e)}")
            raise
    
    async def save_analysis_result(
        self, 
        file_path: str, 
        result_data: Dict[str, Any]
    ) -> str:
        """
        Save analysis result with version tracking
        
        Args:
            file_path: Original audio file path
            result_data: Analysis result data
            
        Returns:
            Version identifier (e.g., "v1", "v2")
        """
        try:
            audio_name = Path(file_path).stem
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Find existing versions
            existing_versions = list(self.results_dir.glob(f"{audio_name}_v*_*.json"))
            version_num = len(existing_versions) + 1
            
            # Create versioned filename
            result_filename = f"{audio_name}_v{version_num}_{timestamp}.json"
            result_path = self.results_dir / result_filename
            
            # Add version info to result data
            result_data['version'] = version_num
            result_data['version_timestamp'] = timestamp
            
            # Save as JSON
            async with aiofiles.open(result_path, 'w') as f:
                await f.write(json.dumps(result_data, indent=2))
            
            logger.info(f"Analysis result saved: {result_filename} (version {version_num})")
            
            return f"v{version_num}"
            
        except Exception as e:
            logger.error(f"Error saving analysis result: {str(e)}")
            raise
    
    def get_analysis_result(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Get the most recent analysis result for a file
        
        Args:
            file_path: Original audio file path
            
        Returns:
            Analysis result data or None if not found
        """
        try:
            audio_name = Path(file_path).stem
            
            # Find all results for this file
            matching_results = list(self.results_dir.glob(f"{audio_name}_*.json"))
            
            if not matching_results:
                return None
            
            # Get most recent
            latest_result = max(matching_results, key=lambda p: p.stat().st_mtime)
            
            with open(latest_result, 'r') as f:
                return json.load(f)
                
        except Exception as e:
            logger.error(f"Error retrieving analysis result: {str(e)}")
            return None
    
    def get_recent_results(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent analysis results
        
        Args:
            limit: Maximum number of results to return
            
        Returns:
            List of analysis results, most recent first
        """
        try:
            result_files = list(self.results_dir.glob("*.json"))
            
            # Sort by modification time, most recent first
            result_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            
            results = []
            for result_file in result_files[:limit]:
                try:
                    with open(result_file, 'r') as f:
                        data = json.load(f)
                        # Add metadata
                        data['result_file'] = result_file.name
                        data['saved_at'] = datetime.fromtimestamp(
                            result_file.stat().st_mtime
                        ).isoformat()
                        results.append(data)
                except Exception as e:
                    logger.warning(f"Error reading result file {result_file}: {str(e)}")
                    continue
            
            return results
            
        except Exception as e:
            logger.error(f"Error retrieving recent results: {str(e)}")
            return []
    
    def get_all_versions(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Get all analysis versions for a file
        
        Args:
            file_path: Original audio file path
        
        Returns:
            List of versions, newest first
        """
        try:
            audio_name = Path(file_path).stem
            
            # Find all versions
            version_files = list(self.results_dir.glob(f"{audio_name}_v*_*.json"))
            
            versions = []
            for vfile in version_files:
                try:
                    with open(vfile, 'r') as f:
                        data = json.load(f)
                        versions.append({
                            'filename': vfile.name,
                            'version': data.get('version', 0),
                            'timestamp': data.get('timestamp'),
                            'processing_time': data.get('processing_time'),
                            'version_timestamp': data.get('version_timestamp')
                        })
                except Exception as e:
                    logger.warning(f"Error reading version file {vfile}: {str(e)}")
                    continue
            
            # Sort by version number, newest first
            versions.sort(key=lambda x: x['version'], reverse=True)
            
            return versions
            
        except Exception as e:
            logger.error(f"Error retrieving versions: {str(e)}")
            return []
    
    def get_analysis_result_by_version(self, file_path: str, version: int) -> Optional[Dict[str, Any]]:
        """
        Get specific version of analysis result
        
        Args:
            file_path: Original audio file path
            version: Version number to retrieve
        
        Returns:
            Analysis result data or None if not found
        """
        try:
            audio_name = Path(file_path).stem
            
            # Find the version file
            version_files = list(self.results_dir.glob(f"{audio_name}_v{version}_*.json"))
            
            if not version_files:
                logger.warning(f"No version {version} found for {file_path}")
                return None
            
            # Get most recent if multiple exist with same version
            latest_version = max(version_files, key=lambda p: p.stat().st_mtime)
            
            with open(latest_version, 'r') as f:
                return json.load(f)
                
        except Exception as e:
            logger.error(f"Error retrieving version {version}: {str(e)}")
            return None

