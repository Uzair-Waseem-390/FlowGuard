# import google.generativeai as genai
# from typing import Dict, Any, List, Optional
# import json
# from core import security
# from core.config import settings
# from schemas.schema_schemas import Agent1Output
# import logging

# logger = logging.getLogger(__name__)

# class Agent1Service:
#     """
#     Agent 1: Schema Analysis & Test Generation
#     Uses Gemini 2.5 Flash
#     """
    
#     def __init__(self, gemini_api_key: str):
#         """Initialize with user's Gemini API key"""
#         genai.configure(api_key=gemini_api_key)
#         self.model = genai.GenerativeModel('gemini-2.0-flash')
    
#     def analyze_schema(self, raw_schema: Dict[str, Any], base_url: str) -> Agent1Output:
#         """
#         Analyze schema using Gemini 2.5 Flash
#         Returns normalized schema and test cases
#         """
        
#         # Prepare the prompt exactly as per FlowGuard spec
#         prompt = f"""
#         You are Agent 1 in FlowGuard - an API testing system.
        
#         **TASK:**
#         1. Analyze this OpenAPI schema
#         2. Normalize non-critical information (field names, types, descriptions)
#         3. Validate that CRITICAL information exists
#         4. Generate failure-oriented test cases
        
#         **RULES (STRICT - DO NOT VIOLATE):**
#         - ❌ DO NOT invent endpoints
#         - ❌ DO NOT guess HTTP methods
#         - ❌ DO NOT guess base URL (use: {base_url})
#         - ❌ DO NOT hallucinate authentication
#         - ✅ Infer ONLY non-critical information
        
#         **CRITICAL INFORMATION (MUST EXIST or REJECT):**
#         - Endpoint path (e.g., /users)
#         - HTTP method (GET, POST, etc.)
#         - Request body schema (for POST/PUT)
#         - Response schemas
#         - Base URL: {base_url} (provided by user)
        
#         **INPUT SCHEMA:**
#         {json.dumps(raw_schema, indent=2)}
        
#         **EXPECTED OUTPUT FORMAT (JSON):**
#         {{
#             "status": "ok" or "reject",
#             "normalized_schema": [
#                 {{
#                     "endpoint": "/users",
#                     "method": "GET",
#                     "request_body": {{...}},
#                     "response_schema": {{...}},
#                     "parameters": [...]
#                 }}
#             ],
#             "test_cases": [
#                 {{
#                     "endpoint": "/users",
#                     "method": "GET",
#                     "test_type": "missing_field",
#                     "payload": {{...}},
#                     "expected_failure": true
#                 }}
#             ],
#             "errors": []  # If status=reject, list errors here
#         }}
        
#         **REJECT IF:**
#         - Missing endpoint paths
#         - Missing HTTP methods
#         - Missing request body for POST/PUT
#         - Schema is incomplete or malformed
        
#         **GENERATE TEST CASES FOR:**
#         - Missing required fields
#         - Wrong data types
#         - Boundary values
#         - Malformed data
#         - Authentication bypass attempts
#         - Rate limit testing
#         """
        
#         try:
#             response = self.model.generate_content(prompt)
            
#             # Extract JSON from response
#             response_text = response.text
            
#             # Find JSON in response (Gemini might add explanations)
#             start_idx = response_text.find('{')
#             end_idx = response_text.rfind('}') + 1
            
#             if start_idx == -1 or end_idx == 0:
#                 raise ValueError("No JSON found in AI response")
            
#             json_str = response_text[start_idx:end_idx]
#             result = json.loads(json_str)
            
#             # Validate the structure matches Agent1Output
#             return Agent1Output(**result)
            
#         except json.JSONDecodeError as e:
#             logger.error(f"Failed to parse AI response as JSON: {e}")
#             return Agent1Output(
#                 status="reject",
#                 errors=[f"AI returned invalid JSON: {str(e)}"]
#             )
#         except Exception as e:
#             logger.error(f"Agent 1 failed: {e}")
#             return Agent1Output(
#                 status="reject",
#                 errors=[f"AI processing failed: {str(e)}"]
#             )

# # Helper function to use in routes
# def process_schema_with_agent1(
#     raw_schema: Dict[str, Any], 
#     base_url: str,
#     encrypted_gemini_key: str
# ) -> Agent1Output:
#     """
#     Main function to process schema through Agent 1
#     """
#     try:
#         # Decrypt user's Gemini key
#         gemini_key = security.decrypt_api_key(encrypted_gemini_key)
        
#         # Initialize Agent 1
#         agent1 = Agent1Service(gemini_key)
        
#         # Analyze schema
#         return agent1.analyze_schema(raw_schema, base_url)
        
#     except Exception as e:
#         logger.error(f"Agent 1 processing failed: {e}")
#         return Agent1Output(
#             status="reject",
#             errors=[f"Failed to process schema: {str(e)}"]
#         )



import google.generativeai as genai
from typing import Dict, Any, List, Optional
import json
from core import security
from schemas.schema_schemas import Agent1Output
import logging

logger = logging.getLogger(__name__)

class Agent1Service:
    """
    Agent 1: Schema Analysis & Test Generation
    Uses Gemini 2.5 Flash
    Follows FlowGuard spec section 4
    """
    
    def __init__(self, gemini_api_key: str):
        """Initialize with user's Gemini API key"""
        try:
            genai.configure(api_key=gemini_api_key)
            # Use Gemini 2.5 Flash (or latest Flash model)
            # Note: Model name may vary - using gemini-2.0-flash-exp or gemini-2.0-flash
            # If 2.5 is available, use gemini-2.5-flash
            # Try different model names in order of preference
            model_names = ['gemini-2.0-flash-exp', 'gemini-2.0-flash', 'gemini-1.5-flash']
            self.model = None
            for model_name in model_names:
                try:
                    self.model = genai.GenerativeModel(model_name)
                    logger.info(f"Using Gemini model: {model_name}")
                    break
                except Exception as e:
                    logger.debug(f"Failed to use model {model_name}: {e}")
                    continue
            
            if self.model is None:
                raise ValueError("No valid Gemini Flash model available")
            
            self.valid_key = True
        except Exception as e:
            logger.error(f"Failed to configure Gemini: {e}")
            self.valid_key = False
    
    def analyze_schema(self, raw_schema: Dict[str, Any], base_url: str) -> Agent1Output:
        """
        Analyze schema using Gemini 2.5 Flash
        Returns normalized schema and test cases
        """
        if not self.valid_key:
            return Agent1Output(
                status="reject",
                errors=["Invalid Gemini API key configuration"]
            )
        
        # Prepare the prompt exactly as per FlowGuard spec
        prompt = f"""
        You are Agent 1 in FlowGuard - an API testing system.
        
        **TASK:**
        1. Analyze this OpenAPI schema
        2. Normalize non-critical information (field names, types, descriptions)
        3. Validate that CRITICAL information exists
        4. Generate failure-oriented test cases
        
        **RULES (STRICT - DO NOT VIOLATE):**
        - ❌ DO NOT invent endpoints
        - ❌ DO NOT guess HTTP methods
        - ❌ DO NOT guess base URL (use: {base_url})
        - ❌ DO NOT hallucinate authentication
        - ✅ Infer ONLY non-critical information
        
        **CRITICAL INFORMATION (MUST EXIST or REJECT):**
        - Endpoint path (e.g., /users)
        - HTTP method (GET, POST, etc.)
        - Request body schema (for POST/PUT)
        - Response schemas
        - Base URL: {base_url} (provided by user)
        
        **INPUT SCHEMA:**
        {json.dumps(raw_schema, indent=2)}
        
        **EXPECTED OUTPUT FORMAT (JSON ONLY):**
        {{
            "status": "ok",
            "normalized_schema": [
                {{
                    "endpoint": "/users",
                    "method": "GET",
                    "request_body": {{}},
                    "response_schema": {{}},
                    "parameters": []
                }}
            ],
            "test_cases": [
                {{
                    "endpoint": "/users",
                    "method": "GET",
                    "test_type": "missing_field",
                    "payload": {{}},
                    "expected_failure": true
                }}
            ],
            "errors": []
        }}
        
        **IMPORTANT:**
        - Return ONLY valid JSON
        - No explanations, no markdown, no code blocks
        - If schema is invalid, set status to "reject" and list errors
        
        **REJECT IF:**
        - Missing endpoint paths
        - Missing HTTP methods
        - Missing request body for POST/PUT methods
        - Schema is incomplete or malformed
        
        **GENERATE TEST CASES FOR THESE FAILURE TYPES:**
        1. missing_field - Omit required fields
        2. wrong_type - Send wrong data types
        3. boundary_values - Test min/max boundaries
        4. malformed_json - Send invalid JSON
        5. sql_injection - Attempt SQL injection
        6. xss - Attempt cross-site scripting
        7. rate_limit - Send too many requests
        8. auth_bypass - Try to access without auth
        """
        
        try:
            logger.info("Calling Gemini 2.5 Flash for schema analysis...")
            
            # Generate content
            response = self.model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.1,  # Low for deterministic output
                    "max_output_tokens": 4000,
                }
            )
            
            # Extract JSON from response
            response_text = response.text.strip()
            logger.debug(f"Raw AI response: {response_text[:500]}...")
            
            # Clean the response - remove markdown code blocks if present
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            response_text = response_text.strip()
            
            # Parse JSON
            result = json.loads(response_text)
            
            # Convert to Agent1Output
            return Agent1Output(**result)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            logger.error(f"Response was: {response_text}")
            return Agent1Output(
                status="reject",
                errors=[f"AI returned invalid JSON: {str(e)}"]
            )
        except Exception as e:
            logger.error(f"Agent 1 failed: {e}")
            return Agent1Output(
                status="reject",
                errors=[f"AI processing failed: {str(e)}"]
            )


# Helper function to use in routes
def process_schema_with_agent1(
    raw_schema: Dict[str, Any], 
    base_url: str,
    encrypted_gemini_key: str
) -> Agent1Output:
    """
    Main function to process schema through Agent 1
    """
    try:
        # Decrypt user's Gemini key
        gemini_key = security.decrypt_api_key(encrypted_gemini_key)
        
        # Initialize Agent 1
        agent1 = Agent1Service(gemini_key)
        
        # Analyze schema
        return agent1.analyze_schema(raw_schema, base_url)
        
    except Exception as e:
        logger.error(f"Agent 1 processing failed: {e}")
        return Agent1Output(
            status="reject",
            errors=[f"Failed to process schema: {str(e)}"]
        )