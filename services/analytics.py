"""
Healthcare Analytics Service
Extracts meaningful insights from patient-provider call transcriptions using AI
"""
import re
import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio
from openai import OpenAI
from config import Config

logger = logging.getLogger(__name__)

class HealthcareAnalyticsService:
    """
    Service for analyzing healthcare call transcriptions and extracting key insights using Nemotron AI
    """
    
    def __init__(self, nemotron_client: Optional[OpenAI] = None):
        self.use_ai = Config.NEMOTRON_ENABLED and nemotron_client is not None
        self.client = nemotron_client
        self.model_id = Config.NEMOTRON_MODEL_ID if self.use_ai else None
        
        logger.info(f"HealthcareAnalyticsService initialized - AI extraction: {self.use_ai}")
        # Common medical terms and patterns
        self.medication_patterns = [
            # Pattern 1: Medication mentioned with action words
            r'\b(?:taking|prescribed|medication|medicine|drug|switching to|switch to|recommend|start)\s+([A-Z][a-z]+(?:pril|mine|statin|formin|cillin|mycin|azole|oprazole|dipine|olol|sartan|zepam|xetine|traline|tidine|mycin|cycline))\b',
            # Pattern 2: Medication with dosage
            r'\b([A-Z][a-z]+(?:pril|mine|statin|formin|cillin|mycin|azole|oprazole|dipine|olol|sartan|zepam|xetine|traline|tidine|mycin|cycline))\s+\d+\s*(?:mg|mcg|milligrams?|micrograms?)\b',
            # Pattern 3: Just the medication name alone (capitalized)
            r'\b([A-Z][a-z]{4,}(?:pril|mine|statin|formin|cillin|mycin|azole|oprazole|dipine|olol|sartan|zepam|xetine|traline|tidine|mycin|cycline))\b',
        ]
        
        self.condition_keywords = [
            'diabetes', 'hypertension', 'high blood pressure', 'heart disease',
            'asthma', 'copd', 'depression', 'anxiety', 'arthritis', 'cancer',
            'stroke', 'heart attack', 'chest pain', 'shortness of breath',
            'migraine', 'obesity', 'cholesterol', 'infection', 'pneumonia'
        ]
        
        self.symptom_keywords = [
            'pain', 'fever', 'cough', 'fatigue', 'nausea', 'vomiting',
            'dizziness', 'headache', 'rash', 'swelling', 'bleeding',
            'weakness', 'numbness', 'confusion', 'difficulty breathing'
        ]
        
        self.urgency_keywords = [
            'emergency', 'urgent', 'severe', 'immediately', 'right away',
            'as soon as possible', 'critical', 'serious', 'worse', 'worsening'
        ]
        
    async def analyze_healthcare_call(
        self, 
        transcription: str, 
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze a healthcare call transcription and extract key insights using AI
        
        Returns structured data including:
        - Call type (clinical vs administrative)
        - Participants (doctor/patient identification)
        - Medical conditions mentioned
        - Medications discussed
        - Symptoms reported
        - Follow-up actions
        - Urgency level
        - Sentiment analysis
        - Compliance indicators
        """
        try:
            logger.info("Starting AI-powered healthcare analytics")
            
            if self.use_ai:
                # Use AI for all extraction
                logger.info("Using Nemotron AI for extraction")
                insights = await self._ai_extract_all(transcription)
            else:
                # Fallback to basic extraction
                logger.info("Using basic extraction (AI not available)")
                insights = self._basic_extraction(transcription)
            
            # Add metadata
            insights["analysis_metadata"] = {
                "analyzed_at": datetime.now().isoformat(),
                "transcription_length": len(transcription),
                "word_count": len(transcription.split()),
                "extraction_method": "ai" if self.use_ai else "basic"
            }
            
            logger.info(f"Healthcare analytics completed - Call type: {insights.get('call_type', 'unknown')}")
            return insights
            
        except Exception as e:
            logger.error(f"Analytics error: {str(e)}")
            raise
    
    async def _ai_extract_all(self, transcription: str) -> Dict[str, Any]:
        """Use Nemotron AI to extract all healthcare insights"""
        
        prompt = f"""Analyze this healthcare call transcription and extract structured information.

Transcription:
{transcription}

Extract and return ONLY a valid JSON object with the following structure (no markdown, no explanation):
{{
  "call_type": "clinical" or "administrative" or "general",
  "participants": {{
    "provider_identified": true/false,
    "patient_identified": true/false,
    "provider_name": "name or null",
    "provider_role": "role or null"
  }},
  "call_summary": "1-2 sentence summary of the call",
  "medical_conditions": [
    {{"condition": "name", "context": "relevant quote"}}
  ],
  "medications": [
    {{"name": "medication name", "dosage": "dosage or null", "frequency": "frequency or null", "context": "relevant quote"}}
  ],
  "symptoms": [
    {{"symptom": "symptom name", "context": "relevant quote"}}
  ],
  "follow_up_actions": [
    {{"type": "appointment/prescription/test/other", "description": "action description"}}
  ],
  "urgency_level": {{
    "level": "low/medium/high",
    "score": 0-5,
    "triggers": ["list of urgency indicators"],
    "reason": "brief explanation"
  }},
  "sentiment_analysis": {{
    "overall_sentiment": "positive/negative/neutral",
    "confidence_score": 0.0-1.0,
    "positive_indicators": count,
    "negative_indicators": count
  }},
  "key_topics": ["topic1", "topic2"],
  "compliance_indicators": {{
    "documentation_quality": "excellent/good/needs_improvement/poor",
    "consent_mentioned": true/false,
    "privacy_acknowledged": true/false,
    "patient_understanding_confirmed": true/false,
    "follow_up_scheduled": true/false
  }}
}}

Important:
- Return ONLY valid JSON, no markdown formatting
- Extract actual medication names (e.g., "Lisinopril", "Losartan")
- Include dosages if mentioned (e.g., "10 mg")
- Identify provider names from the transcript (e.g., "Angela", "Dr. Chen")
- Set urgency to "low" unless emergency/urgent keywords present
- For administrative calls about insurance/benefits, set call_type to "administrative"
"""

        try:
            # Run synchronous API call in thread pool
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model=self.model_id,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,  # Low temperature for consistent extraction
                    top_p=0.9,
                    max_tokens=2000,
                    stream=False
                )
            )
            
            content = response.choices[0].message.content.strip()
            
            # Remove markdown code blocks if present
            if content.startswith('```'):
                content = content.split('```')[1]
                if content.startswith('json'):
                    content = content[4:]
            content = content.strip()
            
            # Parse JSON
            insights = json.loads(content)
            
            logger.info("AI extraction completed successfully")
            return insights
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            logger.error(f"Response content: {content[:500] if 'content' in locals() else 'No content'}")
            # Fall back to basic extraction
            return self._basic_extraction(transcription)
        except Exception as e:
            logger.error(f"AI extraction failed: {e}")
            # Fall back to basic extraction
            return self._basic_extraction(transcription)
    
    def _basic_extraction(self, transcription: str) -> Dict[str, Any]:
        """Fallback basic extraction when AI is not available"""
        call_type = self._detect_call_type(transcription)
        
        return {
            "call_type": call_type,
            "participants": self._identify_participants(transcription),
            "call_summary": self._generate_summary(transcription, call_type),
            "medical_conditions": self._extract_conditions(transcription),
            "medications": self._extract_medications(transcription),
            "symptoms": self._extract_symptoms(transcription),
            "follow_up_actions": self._extract_follow_up_actions(transcription),
            "urgency_level": self._assess_urgency(transcription, call_type),
            "sentiment_analysis": self._analyze_sentiment(transcription),
            "key_topics": self._extract_key_topics(transcription),
            "compliance_indicators": self._assess_compliance(transcription)
        }
    
    def _identify_participants(self, text: str) -> Dict[str, Any]:
        """Identify participants in the call"""
        participants = {
            "provider_identified": False,
            "patient_identified": False,
            "provider_name": None,
            "provider_role": None,
        }
        
        # Look for doctor/provider identification
        doctor_patterns = [
            r'(?:Dr\.|Doctor)\s+([A-Z][a-z]+)',
            r'(?:This is|I\'m)\s+(?:Dr\.|Doctor)\s+([A-Z][a-z]+)',
        ]
        
        for pattern in doctor_patterns:
            match = re.search(pattern, text)
            if match:
                participants['provider_identified'] = True
                participants['provider_name'] = f"Dr. {match.group(1)}"
                participants['provider_role'] = 'Doctor'
                break
        
        # Look for named providers (nurses, staff)
        if not participants['provider_identified']:
            provider_name_patterns = [
                r'This is\s+([A-Z][a-z]+)(?:\s+with|\s+from|\.|,)',
                r'I\'m\s+([A-Z][a-z]+)(?:\s+with|\s+from|\.|,)',
                r'calling\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',  # e.g., "calling Riverside Medical"
            ]
            
            for pattern in provider_name_patterns:
                match = re.search(pattern, text)
                if match:
                    name = match.group(1)
                    # Exclude common false positives
                    if name.lower() not in ['patient', 'provider', 'doctor', 'nurse', 'medical', 'health', 'clinic']:
                        participants['provider_identified'] = True
                        participants['provider_name'] = name
                        # Try to determine role
                        if 'nurse' in text.lower():
                            participants['provider_role'] = 'Nurse'
                        elif 'medical' in text.lower() or 'clinic' in text.lower():
                            participants['provider_role'] = 'Medical Staff'
                        break
        
        # Look for patient name
        patient_name_patterns = [
            r'(?:This is|I\'m)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)(?:\.|,|\s+and)',  # Full name
            r'(?:my name is|speaking)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',
        ]
        
        for pattern in patient_name_patterns:
            match = re.search(pattern, text)
            if match:
                participants['patient_identified'] = True
                break
        
        # Patient is identified if there's a dialogue
        if not participants['patient_identified'] and re.search(r'Patient:', text, re.IGNORECASE):
            participants['patient_identified'] = True
        
        return participants
    
    def _extract_medications(self, text: str) -> List[Dict[str, Any]]:
        """Extract medication information"""
        medications = []
        seen = set()
        
        for pattern in self.medication_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                med_name = match.group(1).capitalize()
                if med_name.lower() not in seen:
                    seen.add(med_name.lower())
                    
                    # Try to find dosage
                    dosage_match = re.search(
                        rf'{med_name}\s+(\d+\s*(?:mg|mcg))',
                        text,
                        re.IGNORECASE
                    )
                    dosage = dosage_match.group(1) if dosage_match else None
                    
                    # Try to find frequency
                    frequency_match = re.search(
                        rf'{med_name}.*?(\d+\s*times?\s*(?:daily|day|per day)|daily|twice daily|once daily)',
                        text,
                        re.IGNORECASE
                    )
                    frequency = frequency_match.group(1) if frequency_match else None
                    
                    medications.append({
                        "name": med_name,
                        "dosage": dosage,
                        "frequency": frequency,
                        "context": match.group(0)
                    })
        
        return medications
    
    def _extract_conditions(self, text: str) -> List[Dict[str, str]]:
        """Extract medical conditions mentioned"""
        conditions = []
        text_lower = text.lower()
        seen = set()
        
        for condition in self.condition_keywords:
            if condition in text_lower and condition not in seen:
                seen.add(condition)
                
                # Find context around the condition
                pattern = rf'.{{0,50}}{re.escape(condition)}.{{0,50}}'
                match = re.search(pattern, text, re.IGNORECASE)
                context = match.group(0).strip() if match else condition
                
                conditions.append({
                    "condition": condition.title(),
                    "context": context
                })
        
        return conditions
    
    def _extract_symptoms(self, text: str) -> List[Dict[str, str]]:
        """Extract symptoms reported by patient"""
        symptoms = []
        text_lower = text.lower()
        seen = set()
        
        for symptom in self.symptom_keywords:
            if symptom in text_lower and symptom not in seen:
                seen.add(symptom)
                
                pattern = rf'.{{0,50}}{re.escape(symptom)}.{{0,50}}'
                match = re.search(pattern, text, re.IGNORECASE)
                context = match.group(0).strip() if match else symptom
                
                symptoms.append({
                    "symptom": symptom.title(),
                    "context": context
                })
        
        return symptoms
    
    def _extract_follow_up_actions(self, text: str) -> List[Dict[str, str]]:
        """Extract follow-up actions and appointments"""
        actions = []
        
        # Look for appointments
        appointment_patterns = [
            r'(?:schedule|appointment|come in|see you|follow[- ]up).*?(?:tomorrow|next week|in \d+ days?|on [A-Z][a-z]+)',
            r'(?:tomorrow|next week|in \d+ days?).*?(?:at \d+(?::\d+)?\s*(?:AM|PM|am|pm)?)',
        ]
        
        for pattern in appointment_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                actions.append({
                    "type": "appointment",
                    "description": match.group(0).strip()
                })
        
        # Look for tests/procedures
        test_patterns = [
            r'(?:schedule|order|need|require).*?(?:test|lab|blood work|x-ray|MRI|CT scan|EKG|ECG|ultrasound)',
        ]
        
        for pattern in test_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                actions.append({
                    "type": "diagnostic_test",
                    "description": match.group(0).strip()
                })
        
        # Look for prescriptions
        if re.search(r'prescri(?:be|ption)', text, re.IGNORECASE):
            actions.append({
                "type": "prescription",
                "description": "New prescription(s) to be filled"
            })
        
        return actions
    
    def _detect_call_type(self, text: str) -> str:
        """Detect if this is a clinical, administrative, or sales call"""
        text_lower = text.lower()
        
        # Administrative/Benefits call indicators
        admin_keywords = [
            'insurance', 'medicare', 'medicaid', 'premium', 'co-pay', 'deductible',
            'coverage', 'plan', 'benefits', 'policy', 'enrollment', 'eligibility'
        ]
        
        # Clinical call indicators
        clinical_keywords = [
            'symptom', 'diagnosis', 'treatment', 'prescription', 'test results',
            'examination', 'procedure', 'surgery', 'therapy', 'medical history'
        ]
        
        admin_count = sum(1 for keyword in admin_keywords if keyword in text_lower)
        clinical_count = sum(1 for keyword in clinical_keywords if keyword in text_lower)
        
        # If significant admin keywords and few clinical, it's administrative
        if admin_count >= 3 and admin_count > clinical_count * 2:
            return "administrative"
        elif clinical_count >= 2:
            return "clinical"
        else:
            return "general"
    
    def _assess_urgency(self, text: str, call_type: str = "general") -> Dict[str, Any]:
        """Assess the urgency level of the call"""
        text_lower = text.lower()
        urgency_score = 0
        triggers = []
        
        # Administrative calls are never urgent
        if call_type == "administrative":
            return {
                "level": "low",
                "score": 0,
                "triggers": [],
                "reason": "Administrative call"
            }
        
        for keyword in self.urgency_keywords:
            if keyword in text_lower:
                urgency_score += 1
                triggers.append(keyword)
        
        # Check for emergency room mentions (only if it's about GOING to ER, not just mentioning it)
        er_patterns = [
            r'go(?:ing)? to (?:the )?(?:emergency room|ER)',
            r'need(?:s)? to go to (?:the )?(?:emergency room|ER)',
            r'visit(?:ing)? (?:the )?(?:emergency room|ER)',
            r'call(?:ing)? 911',
            r'going to 911'
        ]
        
        for pattern in er_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                urgency_score += 3
                triggers.append("emergency_visit_needed")
                break
        
        # Determine level
        if urgency_score >= 3:
            level = "high"
        elif urgency_score >= 1:
            level = "medium"
        else:
            level = "low"
        
        return {
            "level": level,
            "score": urgency_score,
            "triggers": triggers
        }
    
    def _analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Basic sentiment analysis of the call"""
        # Simple keyword-based sentiment
        positive_words = ['good', 'better', 'improving', 'great', 'excellent', 'thank']
        negative_words = ['pain', 'worse', 'bad', 'severe', 'worried', 'concerned', 'difficult']
        
        text_lower = text.lower()
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        total = positive_count + negative_count
        if total == 0:
            sentiment = "neutral"
            score = 0.5
        else:
            score = positive_count / total
            if score > 0.6:
                sentiment = "positive"
            elif score < 0.4:
                sentiment = "negative"
            else:
                sentiment = "neutral"
        
        return {
            "overall_sentiment": sentiment,
            "confidence_score": score,
            "positive_indicators": positive_count,
            "negative_indicators": negative_count
        }
    
    def _extract_key_topics(self, text: str) -> List[str]:
        """Extract key topics discussed in the call"""
        topics = []
        
        topic_keywords = {
            "medication_management": ["medication", "prescription", "drug", "dose", "taking"],
            "diagnostic_testing": ["test", "lab", "blood work", "x-ray", "scan"],
            "symptom_discussion": ["symptom", "pain", "feeling", "experiencing"],
            "treatment_plan": ["treatment", "plan", "therapy", "procedure"],
            "follow_up_care": ["follow up", "come back", "appointment", "see you"],
            "lifestyle_counseling": ["diet", "exercise", "lifestyle", "weight", "smoking"],
            "referral": ["specialist", "referral", "see another doctor"],
        }
        
        text_lower = text.lower()
        for topic, keywords in topic_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                topics.append(topic.replace("_", " ").title())
        
        return topics
    
    def _assess_compliance(self, text: str) -> Dict[str, Any]:
        """Assess documentation and compliance indicators"""
        compliance = {
            "documentation_quality": "good",
            "consent_mentioned": False,
            "privacy_acknowledged": False,
            "patient_understanding_confirmed": False,
            "follow_up_scheduled": False,
        }
        
        text_lower = text.lower()
        
        # Check for consent
        if re.search(r'consent|agree|permission', text_lower):
            compliance['consent_mentioned'] = True
        
        # Check for privacy/HIPAA
        if re.search(r'privacy|confidential|hipaa', text_lower):
            compliance['privacy_acknowledged'] = True
        
        # Check for patient understanding
        if re.search(r'do you understand|any questions|make sense|clear', text_lower):
            compliance['patient_understanding_confirmed'] = True
        
        # Check for follow-up
        if re.search(r'follow[- ]up|appointment|come back|see you', text_lower):
            compliance['follow_up_scheduled'] = True
        
        # Overall quality assessment
        compliance_score = sum([
            compliance['consent_mentioned'],
            compliance['privacy_acknowledged'],
            compliance['patient_understanding_confirmed'],
            compliance['follow_up_scheduled']
        ])
        
        if compliance_score >= 3:
            compliance['documentation_quality'] = "excellent"
        elif compliance_score >= 2:
            compliance['documentation_quality'] = "good"
        else:
            compliance['documentation_quality'] = "needs_improvement"
        
        return compliance
    
    def _generate_summary(self, text: str, call_type: str = "general") -> str:
        """Generate a brief summary of the call"""
        # For administrative calls, provide appropriate context
        if call_type == "administrative":
            text_lower = text.lower()
            if "medicare" in text_lower or "medicaid" in text_lower:
                return "Administrative call regarding Medicare/Medicaid benefits, coverage options, and eligibility verification."
            elif "insurance" in text_lower and ("coverage" in text_lower or "benefits" in text_lower):
                return "Administrative call regarding health insurance coverage, benefits review, and plan options."
        
        # Extract first and last sentences for context
        sentences = [s.strip() for s in text.split('.') if s.strip()]
        
        if len(sentences) <= 3:
            return text[:200] + "..." if len(text) > 200 else text
        
        # Create summary from key sentences
        summary_parts = [
            sentences[0],  # Opening
        ]
        
        # Add middle context if available
        if len(sentences) > 4:
            summary_parts.append(sentences[len(sentences)//2])
        
        # Add closing
        if sentences[-1]:
            summary_parts.append(sentences[-1])
        
        summary = ". ".join(summary_parts) + "."
        
        # Limit length
        if len(summary) > 300:
            summary = summary[:297] + "..."
        
        return summary

