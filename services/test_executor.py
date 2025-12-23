import aiohttp
import asyncio
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import logging
from enum import Enum

logger = logging.getLogger(__name__)

class TestResult(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    TIMEOUT = "timeout"

class TestExecutor:
    """
    Test Execution Engine (NO AI HERE)
    Executes test cases against the target API
    Follows FlowGuard spec section 7
    """
    
    def __init__(self, base_url: str, timeout: int = 10, max_concurrent: int = 5):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.max_concurrent = max_concurrent
        self.session = None
    
    async def __aenter__(self):
        """Async context manager for session"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup session"""
        if self.session:
            await self.session.close()
    
    async def execute_test_case(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a single test case
        Returns: {
            "test_case": original test case,
            "status_code": int,
            "response_body": str (sanitized),
            "response_time_ms": float,
            "headers": dict (safe only),
            "result": TestResult,
            "failure_reason": Optional[str]
        }
        """
        start_time = datetime.now()
        
        try:
            # Build request URL
            endpoint = test_case.get('endpoint', '')
            url = f"{self.base_url}{endpoint}"
            
            # Prepare request data
            method = test_case.get('method', 'GET').upper()
            payload = test_case.get('payload', {})
            headers = test_case.get('headers', {})
            
            # Default headers
            if 'Content-Type' not in headers and payload:
                headers['Content-Type'] = 'application/json'
            
            # Execute request
            async with self.session.request(
                method=method,
                url=url,
                json=payload if payload else None,
                headers=headers
            ) as response:
                
                # Read response
                response_body = await response.text()
                response_time = (datetime.now() - start_time).total_seconds() * 1000
                
                # Sanitize response (don't log sensitive data)
                sanitized_body = self._sanitize_response(response_body)
                
                # Determine result
                result, failure_reason = self._analyze_response(
                    response.status,
                    sanitized_body,
                    response_time,
                    test_case
                )
                
                return {
                    "test_case": test_case,
                    "status_code": response.status,
                    "response_body": sanitized_body[:500],  # Trim to 500 chars
                    "response_time_ms": round(response_time, 2),
                    "headers": self._get_safe_headers(response.headers),
                    "result": result,
                    "failure_reason": failure_reason
                }
                
        except asyncio.TimeoutError:
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            return {
                "test_case": test_case,
                "status_code": None,
                "response_body": "",
                "response_time_ms": round(response_time, 2),
                "headers": {},
                "result": TestResult.TIMEOUT,
                "failure_reason": "Request timeout"
            }
        except Exception as e:
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"Test execution error: {e}")
            return {
                "test_case": test_case,
                "status_code": None,
                "response_body": "",
                "response_time_ms": round(response_time, 2),
                "headers": {},
                "result": TestResult.ERROR,
                "failure_reason": f"Execution error: {str(e)}"
            }
    
    async def execute_test_suite(self, test_cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Execute all test cases with concurrency control
        """
        if not self.session:
            async with self:
                return await self._execute_concurrently(test_cases)
        return await self._execute_concurrently(test_cases)
    
    async def _execute_concurrently(self, test_cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Execute tests with limited concurrency"""
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def execute_with_semaphore(test_case):
            async with semaphore:
                return await self.execute_test_case(test_case)
        
        tasks = [execute_with_semaphore(tc) for tc in test_cases]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Task {i} failed: {result}")
                final_results.append({
                    "test_case": test_cases[i],
                    "status_code": None,
                    "response_body": "",
                    "response_time_ms": 0,
                    "headers": {},
                    "result": TestResult.ERROR,
                    "failure_reason": f"Task execution failed: {str(result)}"
                })
            else:
                final_results.append(result)
        
        return final_results
    
    def _sanitize_response(self, response_body: str) -> str:
        """
        Sanitize response to remove sensitive data
        Per spec: DO NOT log sensitive responses
        """
        if not response_body:
            return ""
        
        try:
            data = json.loads(response_body)
            
            # Remove potential sensitive fields
            sensitive_keys = ['password', 'token', 'secret', 'key', 'authorization',
                            'credit_card', 'ssn', 'phone', 'email', 'address']
            
            def sanitize_dict(obj):
                if isinstance(obj, dict):
                    for key in list(obj.keys()):
                        if any(sensitive in key.lower() for sensitive in sensitive_keys):
                            obj[key] = "***REDACTED***"
                        elif isinstance(obj[key], (dict, list)):
                            obj[key] = sanitize_dict(obj[key])
                elif isinstance(obj, list):
                    return [sanitize_dict(item) for item in obj]
                return obj
            
            sanitized = sanitize_dict(data)
            return json.dumps(sanitized, indent=2)
        except:
            # If not JSON, return as-is but truncated
            return response_body[:1000]
    
    def _get_safe_headers(self, headers: Dict) -> Dict:
        """Extract only safe headers (no sensitive data)"""
        safe_headers = {}
        safe_header_names = ['content-type', 'content-length', 'server', 'date', 
                           'cache-control', 'x-request-id', 'x-response-time']
        
        for key, value in headers.items():
            if key.lower() in safe_header_names:
                safe_headers[key] = value
        return safe_headers
    
    def _analyze_response(self, status_code: int, response_body: str, 
                         response_time: float, test_case: Dict) -> Tuple[TestResult, Optional[str]]:
        """
        Rule-based failure detection (NO AI)
        Per FlowGuard spec section 8
        """
        test_type = test_case.get('test_type', '')
        expected_failure = test_case.get('expected_failure', False)
        
        # Rule 1: 5xx errors are failures
        if status_code >= 500:
            return TestResult.FAILED, f"5xx Server Error ({status_code})"
        
        # Rule 2: Timeout detection (handled in execute_test_case)
        
        # Rule 3: Invalid success (bad input accepted when it shouldn't be)
        if expected_failure and status_code < 400:
            # Test expected to fail but API accepted it
            return TestResult.FAILED, "Invalid success - bad input was accepted"
        
        # Rule 4: Stack trace or sensitive info leakage
        if self._detects_stack_trace(response_body):
            return TestResult.FAILED, "Stack trace or sensitive info leaked"
        
        # Rule 5: Based on test type
        if test_type == 'sql_injection' and status_code < 400:
            return TestResult.FAILED, "SQL injection attempt succeeded"
        
        if test_type == 'xss' and status_code < 400:
            return TestResult.FAILED, "XSS attempt succeeded"
        
        # Default: passed
        return TestResult.PASSED, None
    
    def _detects_stack_trace(self, response_body: str) -> bool:
        """Check for stack traces or sensitive info"""
        stack_trace_indicators = [
            "Traceback", "at line", "File \"", "Exception:",
            "java.lang.", "System.Exception", "stack trace",
            "error occurred", "internal server error"
        ]
        
        response_lower = response_body.lower()
        return any(indicator.lower() in response_lower for indicator in stack_trace_indicators)


# Synchronous wrapper for use in FastAPI endpoints
async def run_test_suite(schema_id: int, db, current_user) -> Dict[str, Any]:
    """
    Main function to run a test suite
    Returns summary of execution
    """
    from core import models
    
    # Get schema and test cases
    schema = db.query(models.APISchema).filter(
        models.APISchema.schema_id == schema_id,
        models.APISchema.user_id == current_user.user_id
    ).first()
    
    if not schema:
        raise ValueError(f"Schema {schema_id} not found for user")
    
    # Create test run record
    test_run = models.TestRun(
        schema_id=schema_id,
        user_id=current_user.user_id,
        status=models.TestStatus.RUNNING,
        total_tests=len(schema.test_cases),
        started_at=datetime.now()
    )
    db.add(test_run)
    db.commit()
    db.refresh(test_run)
    
    try:
        # Execute all test cases
        async with TestExecutor(base_url=schema.base_url) as executor:
            results = await executor.execute_test_suite(schema.test_cases)
        
        # Process results
        passed = 0
        failed = 0
        errors = 0
        failures_to_analyze = []
        
        for result in results:
            # Count results
            if result['result'] == TestResult.PASSED:
                passed += 1
            elif result['result'] == TestResult.FAILED:
                failed += 1
                failures_to_analyze.append(result)
            else:
                errors += 1
            
            # Store failures in database (for Agent 2)
            if result['result'] in [TestResult.FAILED, TestResult.ERROR, TestResult.TIMEOUT]:
                failure = models.TestFailure(
                    run_id=test_run.run_id,
                    endpoint=result['test_case'].get('endpoint', ''),
                    http_method=result['test_case'].get('method', 'GET'),
                    test_type=result['test_case'].get('test_type', 'unknown'),
                    request_payload=result['test_case'].get('payload'),
                    response_snippet=result['response_body'],
                    status_code=result['status_code'],
                    response_time_ms=result['response_time_ms'],
                    failure_reason=result['failure_reason'] or "Unknown failure"
                )
                db.add(failure)
        
        # Update test run
        test_run.passed_tests = passed
        test_run.failed_tests = failed
        test_run.error_tests = errors
        test_run.completed_at = datetime.now()
        test_run.status = models.TestStatus.COMPLETED
        
        # Track that Agent 1 was used (since we're using its test cases)
        test_run.agent1_called = True
        
        db.commit()
        
        return {
            "run_id": test_run.run_id,
            "total_tests": len(results),
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "failures_to_analyze": failures_to_analyze,
            "all_results": results,  # Include all results for stability score calculation
            "test_run": test_run
        }
        
    except Exception as e:
        # Mark test run as error
        test_run.status = models.TestStatus.ERROR
        test_run.completed_at = datetime.now()
        db.commit()
        
        logger.error(f"Test suite execution failed: {e}")
        raise