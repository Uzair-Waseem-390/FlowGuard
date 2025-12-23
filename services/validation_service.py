# from typing import Dict, Any, List, Tuple
# import re
# from enum import Enum

# class HTTPMethod(str, Enum):
#     GET = "GET"
#     POST = "POST"
#     PUT = "PUT"
#     DELETE = "DELETE"
#     PATCH = "PATCH"

# class ValidationService:
#     """
#     Deterministic validation layer (NO AI)
#     Validates Agent 1 output before DB save
#     """
    
#     @staticmethod
#     def validate_agent1_output(agent_output: Dict[str, Any], base_url: str) -> Tuple[bool, List[str]]:
#         """
#         Validate Agent 1 output per FlowGuard spec section 5
        
#         Returns: (is_valid, errors)
#         """
#         errors = []
        
#         # 1. Check required fields exist
#         required_fields = ['status', 'normalized_schema', 'test_cases', 'errors']
#         for field in required_fields:
#             if field not in agent_output:
#                 errors.append(f"Missing required field: {field}")
        
#         # If status is reject, we don't need further validation
#         if agent_output.get('status') == 'reject':
#             return (False, errors if errors else ["Schema rejected by AI"])
        
#         # 2. Validate normalized_schema structure
#         normalized_schema = agent_output.get('normalized_schema', [])
#         if not isinstance(normalized_schema, list):
#             errors.append("normalized_schema must be a list")
#         else:
#             for idx, endpoint in enumerate(normalized_schema):
#                 if not isinstance(endpoint, dict):
#                     errors.append(f"Endpoint at index {idx} must be a dictionary")
#                     continue
                
#                 # Check critical fields
#                 if 'endpoint' not in endpoint:
#                     errors.append(f"Endpoint at index {idx} missing 'endpoint'")
#                 elif not endpoint['endpoint'].startswith('/'):
#                     errors.append(f"Endpoint path must start with '/': {endpoint['endpoint']}")
                
#                 if 'method' not in endpoint:
#                     errors.append(f"Endpoint at index {idx} missing 'method'")
#                 elif endpoint['method'] not in [m.value for m in HTTPMethod]:
#                     errors.append(f"Invalid HTTP method: {endpoint['method']}")
        
#         # 3. Validate test cases
#         test_cases = agent_output.get('test_cases', [])
#         if not isinstance(test_cases, list):
#             errors.append("test_cases must be a list")
#         else:
#             for idx, test in enumerate(test_cases):
#                 if not isinstance(test, dict):
#                     errors.append(f"Test case at index {idx} must be a dictionary")
#                     continue
                
#                 required_test_fields = ['endpoint', 'method', 'test_type', 'expected_failure']
#                 for field in required_test_fields:
#                     if field not in test:
#                         errors.append(f"Test case at index {idx} missing '{field}'")
        
#         # 4. Check for hallucinated endpoints (endpoints not in schema)
#         if normalized_schema and test_cases:
#             schema_endpoints = set([e.get('endpoint', '') for e in normalized_schema])
#             test_endpoints = set([t.get('endpoint', '') for t in test_cases])
            
#             hallucinated = test_endpoints - schema_endpoints
#             if hallucinated:
#                 errors.append(f"Test cases contain hallucinated endpoints: {list(hallucinated)}")
        
#         return (len(errors) == 0, errors)
    
#     @staticmethod
#     def validate_base_url(base_url: str) -> bool:
#         """Validate base URL format"""
#         pattern = r'^https?://[a-zA-Z0-9.-]+(?::\d+)?(?:/.*)?$'
#         return bool(re.match(pattern, base_url))

from typing import Dict, Any, List, Tuple, Optional
import re
from enum import Enum
import json

class HTTPMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"

class ValidationService:
    """
    Deterministic validation layer (NO AI)
    Validates Agent 1 output before DB save
    Per FlowGuard spec section 5
    """
    
    @staticmethod
    def validate_agent1_output(agent_output: Dict[str, Any], base_url: str) -> Tuple[bool, List[str]]:
        """
        Validate Agent 1 output
        
        Returns: (is_valid, errors)
        """
        errors = []
        
        # 1. Check required fields exist
        required_fields = ['status', 'normalized_schema', 'test_cases', 'errors']
        for field in required_fields:
            if field not in agent_output:
                errors.append(f"Missing required field: {field}")
        
        # If status is reject, we don't need further validation
        if agent_output.get('status') == 'reject':
            if not errors:
                errors.append("Schema rejected by AI")
            return (False, errors)
        
        # Must have status = "ok"
        if agent_output.get('status') != 'ok':
            errors.append(f"Invalid status: {agent_output.get('status')}. Expected 'ok'")
        
        # 2. Validate normalized_schema structure
        normalized_schema = agent_output.get('normalized_schema', [])
        if not isinstance(normalized_schema, list):
            errors.append("normalized_schema must be a list")
        elif len(normalized_schema) == 0:
            errors.append("normalized_schema cannot be empty")
        else:
            for idx, endpoint in enumerate(normalized_schema):
                if not isinstance(endpoint, dict):
                    errors.append(f"Endpoint at index {idx} must be a dictionary")
                    continue
                
                # Check critical fields
                if 'endpoint' not in endpoint:
                    errors.append(f"Endpoint at index {idx} missing 'endpoint'")
                else:
                    endpoint_path = endpoint['endpoint']
                    if not isinstance(endpoint_path, str):
                        errors.append(f"Endpoint path must be string at index {idx}")
                    elif not endpoint_path.startswith('/'):
                        errors.append(f"Endpoint path must start with '/': {endpoint_path}")
                
                if 'method' not in endpoint:
                    errors.append(f"Endpoint at index {idx} missing 'method'")
                else:
                    method = endpoint['method'].upper()
                    if method not in [m.value for m in HTTPMethod]:
                        errors.append(f"Invalid HTTP method at index {idx}: {method}")
                    # Update with uppercase
                    endpoint['method'] = method
                
                # For POST/PUT/PATCH, should have request_body (can be empty dict)
                if endpoint.get('method') in ['POST', 'PUT', 'PATCH']:
                    if 'request_body' not in endpoint:
                        errors.append(f"Endpoint {endpoint.get('endpoint')} ({endpoint.get('method')}) missing 'request_body'")
        
        # 3. Validate test cases
        test_cases = agent_output.get('test_cases', [])
        if not isinstance(test_cases, list):
            errors.append("test_cases must be a list")
        elif len(test_cases) == 0:
            errors.append("test_cases cannot be empty")
        else:
            for idx, test in enumerate(test_cases):
                if not isinstance(test, dict):
                    errors.append(f"Test case at index {idx} must be a dictionary")
                    continue
                
                required_test_fields = ['endpoint', 'method', 'test_type', 'expected_failure']
                for field in required_test_fields:
                    if field not in test:
                        errors.append(f"Test case at index {idx} missing '{field}'")
                
                # Validate test_type
                if 'test_type' in test:
                    valid_test_types = [
                        'missing_field', 'wrong_type', 'boundary_values',
                        'malformed_json', 'sql_injection', 'xss',
                        'rate_limit', 'auth_bypass', 'timeout', 'invalid_auth'
                    ]
                    if test['test_type'] not in valid_test_types:
                        errors.append(f"Invalid test_type at index {idx}: {test['test_type']}")
                
                # Validate method
                if 'method' in test:
                    method = test['method'].upper()
                    if method not in [m.value for m in HTTPMethod]:
                        errors.append(f"Invalid HTTP method in test case {idx}: {method}")
                    test['method'] = method
        
        # 4. Check for hallucinated endpoints (test cases for non-existent endpoints)
        if normalized_schema and test_cases:
            # Get all endpoints from normalized schema
            schema_endpoints = set()
            for endpoint in normalized_schema:
                if 'endpoint' in endpoint:
                    schema_endpoints.add(endpoint['endpoint'])
            
            # Check each test case
            for idx, test in enumerate(test_cases):
                test_endpoint = test.get('endpoint', '')
                if test_endpoint and test_endpoint not in schema_endpoints:
                    errors.append(f"Test case {idx} references non-existent endpoint: {test_endpoint}")
        
        # 5. Validate errors field
        errors_field = agent_output.get('errors', [])
        if not isinstance(errors_field, list):
            errors.append("errors field must be a list")
        
        return (len(errors) == 0, errors)
    
    @staticmethod
    def validate_base_url(base_url: str) -> bool:
        """Validate base URL format"""
        if not base_url or not isinstance(base_url, str):
            return False
        
        # Remove trailing slash for consistency
        base_url = base_url.rstrip('/')
        
        pattern = r'^https?://[a-zA-Z0-9.-]+(?::\d+)?(?:/.*)?$'
        return bool(re.match(pattern, base_url))
    
    @staticmethod
    def calculate_schema_hash(schema_content: Dict[str, Any], base_url: str) -> str:
        """Calculate SHA256 hash of schema + base URL for caching"""
        import hashlib
        
        # Sort keys for consistent hashing
        sorted_schema = json.dumps(schema_content, sort_keys=True)
        content_str = sorted_schema + base_url
        
        return hashlib.sha256(content_str.encode()).hexdigest()