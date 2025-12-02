"""
Nemotron LLM Summarization Service
Uses NVIDIA Nemotron for enhanced call summarization and insights
"""
import asyncio
import logging
from typing import Dict, Any
from openai import OpenAI
from config import Config

logger = logging.getLogger(__name__)

class NemotronSummarizationService:
    """
    Service for enhanced summarization using Nemotron LLM
    """
    
    def __init__(self):
        self.enabled = Config.NEMOTRON_ENABLED
        self.base_url = Config.NEMOTRON_BASE_URL
        self.model_id = Config.NEMOTRON_MODEL_ID
        
        if self.enabled and self.base_url:
            token = Config.get_cdp_token()
            if token:
                self.client = OpenAI(
                    base_url=self.base_url,
                    api_key=token
                )
                logger.info("Nemotron summarization service initialized")
            else:
                logger.warning("Nemotron enabled but no CDP token available")
                self.enabled = False
        else:
            self.client = None
            logger.info("Nemotron summarization disabled or not configured")
    
    async def generate_enhanced_summary(
        self, 
        transcription: str,
        healthcare_insights: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate enhanced summary using Nemotron LLM
        
        Args:
            transcription: Full call transcription
            healthcare_insights: Extracted healthcare insights
            
        Returns:
            Dictionary with enhanced summaries and insights
        """
        if not self.enabled or not self.client:
            logger.info("Nemotron not available, using basic summary")
            return self._fallback_summary(transcription, healthcare_insights)
        
        try:
            # Run all 4 Nemotron calls concurrently for faster processing
            logger.info("Generating enhanced summaries (4 concurrent AI calls)...")
            results = await asyncio.gather(
                self._generate_call_summary(transcription),
                self._generate_clinical_summary(transcription, healthcare_insights),
                self._generate_key_takeaways(transcription, healthcare_insights),
                self._generate_recommended_actions(transcription, healthcare_insights),
                return_exceptions=True  # Don't fail entire batch if one fails
            )
            
            # Unpack results (handle potential exceptions)
            call_summary = results[0] if not isinstance(results[0], Exception) else "Summary generation failed"
            clinical_summary = results[1] if not isinstance(results[1], Exception) else "Clinical summary generation failed"
            key_takeaways = results[2] if not isinstance(results[2], Exception) else []
            recommended_actions = results[3] if not isinstance(results[3], Exception) else []
            
            logger.info("Enhanced summaries completed (concurrent execution)")
            
            return {
                "call_summary": call_summary,
                "clinical_summary": clinical_summary,
                "key_takeaways": key_takeaways,
                "recommended_actions": recommended_actions,
                "generated_by": "nemotron"
            }
            
        except Exception as e:
            logger.error(f"Error generating Nemotron summary: {str(e)}")
            return self._fallback_summary(transcription, healthcare_insights)
    
    async def _generate_call_summary(self, transcription: str) -> str:
        """Generate a concise call summary"""
        prompt = f"""Summarize this healthcare call in 2-3 sentences. Focus on the main reason for the call, key concerns, and outcome.

Transcription:
{transcription[:3000]}

Provide a concise, professional summary:"""
        
        try:
            # Run sync OpenAI call in thread pool for true concurrency
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model=self.model_id,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                    top_p=0.7,
                    max_tokens=300,
                    stream=False
                )
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error in call summary: {str(e)}")
            return "Summary generation failed"
    
    async def _generate_clinical_summary(
        self, 
        transcription: str,
        insights: Dict[str, Any]
    ) -> str:
        """Generate a detailed clinical summary"""
        
        conditions = ", ".join([c.get('condition', '') for c in insights.get('medical_conditions', [])])
        medications = ", ".join([m.get('name', '') for m in insights.get('medications', [])])
        symptoms = ", ".join([s.get('symptom', '') for s in insights.get('symptoms', [])])
        
        prompt = f"""Create a clinical summary for this healthcare call.

Transcription:
{transcription[:2000]}

Identified Information:
- Conditions: {conditions or 'None'}
- Medications: {medications or 'None'}
- Symptoms: {symptoms or 'None'}

Provide a structured clinical summary covering:
1. Chief complaint
2. Medical history mentioned
3. Current medications
4. Assessment
5. Plan

Clinical Summary:"""
        
        try:
            # Run sync OpenAI call in thread pool for true concurrency
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model=self.model_id,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                    top_p=0.7,
                    max_tokens=500,
                    stream=False
                )
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error in clinical summary: {str(e)}")
            return "Clinical summary generation failed"
    
    async def _generate_key_takeaways(
        self,
        transcription: str,
        insights: Dict[str, Any]
    ) -> list:
        """Generate key takeaways from the call"""
        
        prompt = f"""Extract the 3-5 most important takeaways from this healthcare call.

Transcription:
{transcription[:2000]}

Rules:
- Each takeaway must be a complete, standalone statement
- Each must be actionable or informative
- Do NOT include incomplete sentences or headers without content
- Do NOT end items with colons unless followed by complete information
- Format as simple bullet points

List the key takeaways:"""
        
        try:
            # Run sync OpenAI call in thread pool for true concurrency
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model=self.model_id,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                    top_p=0.7,
                    max_tokens=400,
                    stream=False
                )
            )
            
            # Parse bullet points
            content = response.choices[0].message.content.strip()
            lines = content.split('\n')
            
            takeaways = []
            for line in lines:
                stripped = line.strip().lstrip('•-*0123456789.').strip()
                
                # Skip empty lines
                if not stripped:
                    continue
                    
                # Skip headers/incomplete items (too short or just a colon)
                if len(stripped) < 10:
                    continue
                    
                # Skip items that end with colon and are short (likely headers)
                if stripped.endswith(':') and len(stripped) < 80:
                    continue
                
                takeaways.append(stripped)
            
            return takeaways[:5]  # Limit to 5
            
        except Exception as e:
            logger.error(f"Error in key takeaways: {str(e)}")
            return []
    
    async def _generate_recommended_actions(
        self,
        transcription: str,
        insights: Dict[str, Any]
    ) -> list:
        """Generate recommended follow-up actions"""
        
        follow_ups = insights.get('follow_up_actions', [])
        follow_up_text = ", ".join([f.get('description', '') for f in follow_ups])
        
        prompt = f"""Based on this healthcare call, what are the recommended next steps and actions?

Transcription:
{transcription[:2000]}

Identified follow-ups: {follow_up_text or 'None explicitly mentioned'}

Rules:
- Each action must be complete and specific
- Each should clearly state what to do, who should do it (if applicable), and why
- Do NOT include incomplete sentences, labels, or headers without details
- Do NOT list separate "Action:", "Responsibility:", "Deadline:" as separate items
- Format as simple, complete bullet points

List 3-5 specific, actionable recommendations:"""
        
        try:
            # Run sync OpenAI call in thread pool for true concurrency
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model=self.model_id,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                    top_p=0.7,
                    max_tokens=400,
                    stream=False
                )
            )
            
            # Parse recommendations
            content = response.choices[0].message.content.strip()
            lines = content.split('\n')
            
            actions = []
            for line in lines:
                stripped = line.strip().lstrip('•-*0123456789.').strip()
                
                # Skip empty lines
                if not stripped:
                    continue
                    
                # Skip headers/incomplete items (too short or just labels)
                if len(stripped) < 15:
                    continue
                    
                # Skip single-word labels like "Action:", "Responsibility:", etc.
                if stripped.endswith(':') and len(stripped) < 60:
                    continue
                
                # Skip if it's just "Action" or "Responsibility" etc.
                single_words = ['action', 'responsibility', 'deadline', 'note', 'who', 'what', 'when', 'where']
                if any(stripped.lower().startswith(word + ':') and len(stripped) < 50 for word in single_words):
                    continue
                
                actions.append(stripped)
            
            return actions[:5]  # Limit to 5
            
        except Exception as e:
            logger.error(f"Error in recommended actions: {str(e)}")
            return []
    
    def _fallback_summary(
        self,
        transcription: str,
        insights: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Fallback to basic summary if Nemotron unavailable"""
        return {
            "call_summary": insights.get('call_summary', 'No summary available'),
            "clinical_summary": "Nemotron summarization not available",
            "key_takeaways": [],
            "recommended_actions": [
                f.get('description', '') 
                for f in insights.get('follow_up_actions', [])
            ],
            "generated_by": "basic"
        }

