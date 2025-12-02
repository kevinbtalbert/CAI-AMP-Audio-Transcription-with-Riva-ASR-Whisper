"""
Solr Indexing Service
Handles pushing call analysis data to Cloudera Data Platform Solr
"""
import logging
import requests
import json
import urllib3
from typing import Dict, Any, Optional
from urllib.parse import urljoin
from config import Config

# Disable SSL warnings for CDP environments
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

class SolrIndexer:
    """
    Service for indexing healthcare call analysis data into Solr
    """
    
    def __init__(self):
        self.enabled = Config.SOLR_ENABLED
        self.base_url = Config.SOLR_BASE_URL
        self.collection_name = Config.SOLR_COLLECTION_NAME
        
        if self.enabled and self.base_url:
            token = Config.SOLR_TOKEN
            if token:
                self.headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }
                logger.info(f"Solr indexer initialized - Collection: {self.collection_name}")
            else:
                logger.warning("Solr enabled but no Solr token available")
                self.enabled = False
                self.headers = {}
        else:
            self.headers = {}
            logger.info("Solr indexer disabled or not configured")
    
    def collection_exists(self) -> bool:
        """Check if the Solr collection exists"""
        if not self.enabled:
            return False
        
        try:
            url = urljoin(self.base_url, "admin/collections?action=LIST&wt=json")
            resp = requests.get(url, headers=self.headers, verify=False, timeout=10)
            resp.raise_for_status()
            
            collections = resp.json().get("collections", [])
            exists = self.collection_name in collections
            
            logger.info(f"Collection '{self.collection_name}' exists: {exists}")
            return exists
            
        except Exception as e:
            logger.error(f"Failed to check if collection exists: {e}")
            return False
    
    def create_collection(self) -> bool:
        """Create the Solr collection if it doesn't exist"""
        if not self.enabled:
            raise RuntimeError("Solr is not enabled")
        
        try:
            url = urljoin(
                self.base_url,
                f"admin/collections?action=CREATE&name={self.collection_name}"
                f"&numShards=1&replicationFactor=1&wt=json"
            )
            resp = requests.get(url, headers=self.headers, verify=False, timeout=30)
            resp.raise_for_status()
            
            logger.info(f"Collection '{self.collection_name}' created successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create collection: {e}")
            raise RuntimeError(f"Failed to create Solr collection: {str(e)}")
    
    def enable_auto_fields(self) -> bool:
        """Enable automatic field creation for the collection"""
        if not self.enabled:
            raise RuntimeError("Solr is not enabled")
        
        try:
            url = urljoin(self.base_url, f"{self.collection_name}/config")
            payload = {
                "set-user-property": {
                    "update.autoCreateFields": "true"
                }
            }
            
            resp = requests.post(
                url, 
                headers=self.headers, 
                data=json.dumps(payload), 
                verify=False,
                timeout=10
            )
            resp.raise_for_status()
            
            logger.info(f"Auto field creation enabled for '{self.collection_name}'")
            return True
            
        except Exception as e:
            logger.error(f"Failed to enable auto fields: {e}")
            raise RuntimeError(f"Failed to enable auto fields: {str(e)}")
    
    def ensure_collection_ready(self) -> bool:
        """Ensure collection exists and is properly configured"""
        if not self.enabled:
            return False
        
        try:
            if not self.collection_exists():
                logger.info(f"Collection '{self.collection_name}' does not exist. Creating...")
                self.create_collection()
                self.enable_auto_fields()
                logger.info("Collection created and configured successfully")
            else:
                logger.info(f"Collection '{self.collection_name}' already exists")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to ensure collection is ready: {e}")
            return False
    
    def index_document(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """
        Index a document (call analysis) into Solr
        
        Args:
            document: The analysis result to index
            
        Returns:
            Dictionary with success status and message
        """
        if not self.enabled:
            raise RuntimeError("Solr is not enabled. Please configure Solr in Settings.")
        
        try:
            # Ensure collection is ready
            if not self.ensure_collection_ready():
                raise RuntimeError("Failed to prepare Solr collection")
            
            # Add unique ID if not present
            if 'id' not in document:
                # Use file_path + timestamp as unique ID
                file_path = document.get('file_path', 'unknown')
                timestamp = document.get('timestamp', '')
                document['id'] = f"{file_path}_{timestamp}".replace('/', '_').replace(' ', '_')
            
            # Index the document with commit
            url = urljoin(self.base_url, f"{self.collection_name}/update/json/docs?commit=true")
            
            resp = requests.post(
                url, 
                headers=self.headers, 
                data=json.dumps(document), 
                verify=False,
                timeout=30
            )
            
            if resp.status_code != 200:
                error_msg = f"Solr indexing failed: {resp.text}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            logger.info(f"Document indexed successfully: {document.get('id', 'unknown')}")
            
            return {
                "success": True,
                "message": f"Successfully indexed to Solr collection '{self.collection_name}'",
                "collection": self.collection_name,
                "document_id": document.get('id')
            }
            
        except Exception as e:
            logger.error(f"Failed to index document: {e}")
            return {
                "success": False,
                "message": f"Failed to index document: {str(e)}",
                "error": str(e)
            }
    
    def check_connection(self) -> Dict[str, Any]:
        """
        Check connection to Solr and return status
        
        Returns:
            Dictionary with status information
        """
        if not self.enabled:
            return {
                "status": "disabled",
                "message": "Solr is not enabled"
            }
        
        if not self.base_url:
            return {
                "status": "error",
                "message": "Solr base URL not configured"
            }
        
        try:
            # Try to list collections
            url = urljoin(self.base_url, "admin/collections?action=LIST&wt=json")
            resp = requests.get(url, headers=self.headers, verify=False, timeout=10)
            resp.raise_for_status()
            
            collections = resp.json().get("collections", [])
            collection_ready = self.collection_name in collections
            
            return {
                "status": "online",
                "message": "Connected to Solr",
                "collections_count": len(collections),
                "target_collection": self.collection_name,
                "collection_exists": collection_ready
            }
            
        except requests.exceptions.Timeout:
            return {
                "status": "error",
                "message": "Connection timeout"
            }
        except requests.exceptions.RequestException as e:
            return {
                "status": "error",
                "message": f"Connection failed: {str(e)}"
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error: {str(e)}"
            }
    
    def query_documents(
        self, 
        query: str = "*:*", 
        rows: int = 100,
        start: int = 0,
        sort: str = "timestamp desc",
        filters: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Query documents from Solr collection
        
        Args:
            query: Solr query string (default: all documents)
            rows: Number of results to return
            start: Starting offset for pagination
            sort: Sort order
            filters: Additional filter queries
            
        Returns:
            Dictionary with query results
        """
        if not self.enabled:
            raise RuntimeError("Solr is not enabled")
        
        # Ensure collection exists before querying
        if not self.ensure_collection_ready():
            return {
                "success": False,
                "error": "Collection does not exist and could not be created",
                "numFound": 0,
                "docs": []
            }
        
        try:
            # First check if collection has any documents
            count_url = urljoin(self.base_url, f"{self.collection_name}/select")
            count_resp = requests.get(
                count_url, 
                headers=self.headers, 
                params={"q": "*:*", "rows": 0, "wt": "json"},
                verify=False, 
                timeout=30
            )
            
            if count_resp.status_code == 200:
                count_result = count_resp.json()
                doc_count = count_result.get("response", {}).get("numFound", 0)
                
                if doc_count == 0:
                    logger.info("Collection is empty, returning empty result")
                    return {
                        "success": True,
                        "numFound": 0,
                        "start": 0,
                        "docs": [],
                        "message": "Collection is empty. Push some call analyses to Solr first."
                    }
            
            # Build query parameters
            params = {
                "q": query,
                "rows": rows,
                "start": start,
                "wt": "json"
            }
            
            # Only add sort if collection has documents
            if sort:
                params["sort"] = sort
            
            # Add filter queries if provided
            if filters:
                fq_list = []
                for key, value in filters.items():
                    fq_list.append(f"{key}:{value}")
                if fq_list:
                    params["fq"] = fq_list
            
            url = urljoin(self.base_url, f"{self.collection_name}/select")
            resp = requests.get(url, headers=self.headers, params=params, verify=False, timeout=30)
            resp.raise_for_status()
            
            result = resp.json()
            
            return {
                "success": True,
                "numFound": result.get("response", {}).get("numFound", 0),
                "start": result.get("response", {}).get("start", 0),
                "docs": result.get("response", {}).get("docs", [])
            }
            
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "numFound": 0,
                "docs": [],
                "message": "Query failed. The collection may be empty or fields may not exist yet."
            }
    
    def get_field_stats(self, field: str) -> Dict[str, Any]:
        """
        Get statistics for a specific field
        
        Args:
            field: Field name to get stats for
            
        Returns:
            Dictionary with field statistics
        """
        if not self.enabled:
            raise RuntimeError("Solr is not enabled")
        
        try:
            params = {
                "q": "*:*",
                "rows": 0,
                "stats": "true",
                "stats.field": field,
                "wt": "json"
            }
            
            url = urljoin(self.base_url, f"{self.collection_name}/select")
            resp = requests.get(url, headers=self.headers, params=params, verify=False, timeout=30)
            resp.raise_for_status()
            
            result = resp.json()
            stats = result.get("stats", {}).get("stats_fields", {}).get(field, {})
            
            return {
                "success": True,
                "field": field,
                "stats": stats
            }
            
        except Exception as e:
            logger.error(f"Stats query failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def facet_query(self, facet_field: str, limit: int = 10) -> Dict[str, Any]:
        """
        Get facet counts for a field
        
        Args:
            facet_field: Field to facet on
            limit: Maximum number of facet values to return
            
        Returns:
            Dictionary with facet counts
        """
        if not self.enabled:
            raise RuntimeError("Solr is not enabled")
        
        # Ensure collection exists before querying
        if not self.ensure_collection_ready():
            return {
                "success": False,
                "error": "Collection does not exist",
                "facets": {}
            }
        
        try:
            # First check if collection has any documents
            count_url = urljoin(self.base_url, f"{self.collection_name}/select")
            count_resp = requests.get(
                count_url, 
                headers=self.headers, 
                params={"q": "*:*", "rows": 0, "wt": "json"},
                verify=False, 
                timeout=30
            )
            
            if count_resp.status_code == 200:
                count_result = count_resp.json()
                doc_count = count_result.get("response", {}).get("numFound", 0)
                
                if doc_count == 0:
                    logger.info(f"Collection is empty, returning empty facets for {facet_field}")
                    return {
                        "success": True,
                        "facets": {}
                    }
            
        except Exception as e:
            logger.warning(f"Could not check collection document count: {e}")
        
        try:
            params = {
                "q": "*:*",
                "rows": 0,
                "facet": "true",
                "facet.field": facet_field,
                "facet.limit": limit,
                "facet.mincount": 1,
                "wt": "json"
            }
            
            url = urljoin(self.base_url, f"{self.collection_name}/select")
            resp = requests.get(url, headers=self.headers, params=params, verify=False, timeout=30)
            resp.raise_for_status()
            
            result = resp.json()
            facets = result.get("facet_counts", {}).get("facet_fields", {}).get(facet_field, [])
            
            # Convert flat list [val1, count1, val2, count2] to dict
            facet_dict = {}
            for i in range(0, len(facets), 2):
                if i + 1 < len(facets):
                    facet_dict[facets[i]] = facets[i + 1]
            
            return {
                "success": True,
                "field": facet_field,
                "facets": facet_dict,
                "total_values": len(facet_dict)
            }
            
        except Exception as e:
            logger.error(f"Facet query failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "facets": {}
            }
    
    def get_categorical_facets(self, category: str, limit: int = 20) -> Dict[str, Any]:
        """
        Get facets for categorical data (medications, conditions, symptoms)
        These are stored as nested objects, so we need to query all documents and aggregate
        
        Args:
            category: 'medications', 'conditions', or 'symptoms'
            limit: Maximum number of top items to return
            
        Returns:
            Dictionary with facet counts
        """
        if not self.enabled:
            raise RuntimeError("Solr is not enabled")
        
        try:
            # First check if collection has documents
            count_url = urljoin(self.base_url, f"{self.collection_name}/select")
            count_resp = requests.get(
                count_url,
                headers=self.headers,
                params={"q": "*:*", "rows": 0, "wt": "json"},
                verify=False,
                timeout=30
            )
            
            if count_resp.status_code == 200:
                count_result = count_resp.json()
                doc_count = count_result.get("response", {}).get("numFound", 0)
                
                if doc_count == 0:
                    logger.info(f"Collection is empty, returning empty facets for {category}")
                    return {
                        "success": True,
                        "category": category,
                        "facets": {},
                        "total_values": 0
                    }
            
            # Query all documents (with a reasonable limit) to extract categorical data
            url = urljoin(self.base_url, f"{self.collection_name}/select")
            
            # Determine which specific field to extract based on category
            field_map = {
                "medications": "healthcare_insights.medications.name",
                "conditions": "healthcare_insights.medical_conditions.condition",
                "symptoms": "healthcare_insights.symptoms.symptom"
            }
            target_field = field_map.get(category)
            
            if not target_field:
                raise ValueError(f"Invalid category: {category}")
            
            params = {
                "q": "*:*",
                "rows": 1000,  # Process up to 1000 docs
                "wt": "json",
                "fl": target_field  # Only fetch the specific flattened field we need
            }
            
            logger.info(f"Querying Solr for {category} with field: {target_field}")
            resp = requests.get(url, headers=self.headers, params=params, verify=False, timeout=30)
            resp.raise_for_status()
            
            result = resp.json()
            docs = result.get("response", {}).get("docs", [])
            logger.info(f"Retrieved {len(docs)} documents from Solr")
            
            # Debug: Check if field is in first doc
            if docs:
                logger.info(f"First doc keys: {list(docs[0].keys())}")
                logger.info(f"First doc {target_field}: {docs[0].get(target_field, 'NOT FOUND')}")
            
            # Aggregate categories
            # Note: Solr flattens nested JSON, so fields become "parent.child.field"
            category_counts = {}
            
            for doc in docs:
                # Get the values from the target field (already determined above)
                values = doc.get(target_field, [])
                
                # Ensure it's a list
                if not isinstance(values, list):
                    values = [values]
                
                # Count each value
                for value in values:
                    if value:  # Skip empty/None values
                        category_counts[value] = category_counts.get(value, 0) + 1
            
            # Sort by count and limit
            sorted_categories = dict(
                sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:limit]
            )
            
            logger.info(f"Found {len(sorted_categories)} unique {category}")
            
            return {
                "success": True,
                "category": category,
                "facets": sorted_categories,
                "total_values": len(sorted_categories)
            }
            
        except Exception as e:
            logger.error(f"Categorical facet query failed for {category}: {e}")
            return {
                "success": False,
                "error": str(e),
                "category": category,
                "facets": {}
            }

