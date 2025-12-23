import google.generativeai as genai
from typing import Dict, Any, List, Optional
import json
from core import security
import logging
from enum import Enum

logger = logging.getLogger(__name__)

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class Agent2Service:
    """
    Agent 2: Failure Analysis & Fix Suggestions
    Uses Gemini 2.5 Lite
    Follows FlowGuard spec section 9
    """
    
    def __init__(self, gemini_api_key: str):
        """Initialize with user's Gemini API key"""
        try:
            genai.configure(api_key=gemini_api_key)
            # Use Gemini 2.5 Lite (or latest Lite model)
            # Note: Model name may vary - using gemini-1.5-flash-lite as Lite model
            # If 2.5 Lite is available, use gemini-2.5-lite
            # Try different model names in order of preference
            model_names = ['gemini-1.5-flash-lite', 'gemini-1.5-flash']
            self.model = None
            for model_name in model_names:
                try:
                    self.model = genai.GenerativeModel(model_name)
                    logger.info(f"Using Gemini Lite model: {model_name}")
                    break
                except Exception as e:
                    logger.debug(f"Failed to use model {model_name}: {e}")
                    continue
            
            if self.model is None:
                raise ValueError("No valid Gemini Lite model available")
            
            self.valid_key = True
        except Exception as e:
            logger.error(f"Failed to configure Gemini: {e}")
            self.valid_key = False
    
    def analyze_failure(self, failure_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a single failure and suggest fixes
        
        Input format (per spec section 9):
        {
            "endpoint": "/users",
            "test_type": "missing_field",
            "payload": {...},
            "response_snippet": "...",
            "status_code": 500
        }
        """
        if not self.valid_key:
            return {
                "root_cause": "Gemini API key invalid",
                "risk_level": RiskLevel.HIGH,
                "fix_suggestion": "Check your Gemini API key configuration"
            }
        
        # Prepare the prompt
        prompt = f"""
        You are Agent 2 in FlowGuard - an API failure analysis system.
        
        **TASK:**
        Analyze this API test failure and provide:
        1. Root cause of the failure
        2. Risk level (low, medium, high, critical)
        3. Concrete fix suggestions
        
        **FAILURE DATA:**
        - Endpoint: {failure_data.get('endpoint', 'Unknown')}
        - Test Type: {failure_data.get('test_type', 'Unknown')}
        - Status Code: {failure_data.get('status_code', 'Unknown')}
        
        **REQUEST PAYLOAD:**
        ```json
        {json.dumps(failure_data.get('payload', {}), indent=2)}
        ```
        
        **RESPONSE SNIPPET:**
        ```
        {failure_data.get('response_snippet', 'No response')[:1000]}
        ```
        
        **FAILURE REASON (from rule-based detection):**
        {failure_data.get('failure_reason', 'Unknown')}
        
        **RULES:**
        - Be concise and technical
        - Focus on backend/API issues
        - Suggest actionable fixes
        - Consider security implications
        - Don't suggest UI/UX changes
        
        **RISK LEVEL GUIDE:**
        - LOW: Minor issues, no security impact (e.g., validation message typo)
        - MEDIUM: Functional bugs affecting specific features
        - HIGH: Security vulnerabilities or data integrity issues
        - CRITICAL: System crashes, data loss, severe security breaches
        
        **EXPECTED OUTPUT FORMAT (JSON ONLY):**
        {{
            "root_cause": "Clear explanation of what caused the failure",
            "risk_level": "low/medium/high/critical",
            "fix_suggestion": "Concrete steps to fix the issue"
        }}
        
        **IMPORTANT:**
        - Return ONLY valid JSON
        - No explanations, no markdown, no code blocks
        - Risk level must be one of: low, medium, high, critical
        """
        
        try:
            logger.info("Calling Gemini 2.5 Lite for failure analysis...")
            
            # Generate content
            response = self.model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.1,
                    "max_output_tokens": 1000,  # Keep it short
                }
            )
            
            # Extract JSON from response
            response_text = response.text.strip()
            
            # Clean the response
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            response_text = response_text.strip()
            
            # Parse JSON
            result = json.loads(response_text)
            
            # Validate risk level
            risk = result.get('risk_level', '').lower()
            if risk not in ['low', 'medium', 'high', 'critical']:
                result['risk_level'] = RiskLevel.MEDIUM
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Agent 2 response as JSON: {e}")
            return {
                "root_cause": "Failed to analyze failure",
                "risk_level": RiskLevel.MEDIUM,
                "fix_suggestion": "Check the API logs for more details"
            }
        except Exception as e:
            logger.error(f"Agent 2 failed: {e}")
            return {
                "root_cause": "Analysis failed due to system error",
                "risk_level": RiskLevel.MEDIUM,
                "fix_suggestion": "Retry analysis or check system logs"
            }
    
    def analyze_failures_batch(self, failures_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Analyze multiple failures (one by one)
        """
        results = []
        for failure in failures_data:
            try:
                analysis = self.analyze_failure(failure)
                # Add original failure data to result
                analysis.update({
                    "endpoint": failure.get('endpoint'),
                    "test_type": failure.get('test_type'),
                    "status_code": failure.get('status_code')
                })
                results.append(analysis)
            except Exception as e:
                logger.error(f"Failed to analyze failure: {e}")
                results.append({
                    "endpoint": failure.get('endpoint'),
                    "test_type": failure.get('test_type'),
                    "root_cause": "Analysis failed",
                    "risk_level": RiskLevel.MEDIUM,
                    "fix_suggestion": "Manual investigation required"
                })
        
        return results


# Helper function to use in routes
async def analyze_failures_with_agent2(
    run_id: int,
    encrypted_gemini_key: str,
    db
) -> Dict[str, Any]:
    """
    Main function to analyze failures through Agent 2
    """
    from core import models
    
    try:
        # Decrypt user's Gemini key
        gemini_key = security.decrypt_api_key(encrypted_gemini_key)
        
        # Initialize Agent 2
        agent2 = Agent2Service(gemini_key)
        
        # Get failures from database
        failures = db.query(models.TestFailure).filter(
            models.TestFailure.run_id == run_id,
            models.TestFailure.root_cause.is_(None)  # Only unanalyzed failures
        ).all()
        
        if not failures:
            return {
                "analyzed_count": 0,
                "message": "No failures to analyze"
            }
        
        # Prepare failure data for Agent 2
        failures_data = []
        for failure in failures:
            failures_data.append({
                "endpoint": failure.endpoint,
                "test_type": failure.test_type,
                "payload": failure.request_payload,
                "response_snippet": failure.response_snippet,
                "status_code": failure.status_code,
                "failure_reason": failure.failure_reason
            })
        
        # Analyze failures
        analyses = agent2.analyze_failures_batch(failures_data)
        
        # Update failures with analysis results
        analyzed_count = 0
        for i, analysis in enumerate(analyses):
            if i < len(failures):
                failure = failures[i]
                failure.root_cause = analysis.get('root_cause', '')
                failure.risk_level = analysis.get('risk_level', RiskLevel.MEDIUM)
                failure.fix_suggestion = analysis.get('fix_suggestion', '')
                analyzed_count += 1
        
        # Update test run to indicate Agent 2 was used
        test_run = db.query(models.TestRun).filter(
            models.TestRun.run_id == run_id
        ).first()
        
        if test_run:
            test_run.agent2_called = True
        
        db.commit()
        
        return {
            "analyzed_count": analyzed_count,
            "total_failures": len(failures),
            "analyses": analyses
        }
        
    except Exception as e:
        logger.error(f"Agent 2 processing failed: {e}")
        raise