from typing import Dict, Any, List

def calculate_stability_score(test_results: Dict[str, Any]) -> float:
    """
    Calculate stability score per FlowGuard spec section 10
    Formula: 100 - (5 × num_5xx_errors) - (3 × invalid_successes) - (2 × timeouts)
    
    This function counts all failure types from test results:
    - 5xx errors: Server errors (status >= 500)
    - Invalid successes: Bad input accepted when it shouldn't be
    - Timeouts: Request timeouts
    """
    score = 100.0
    
    # Extract all results (including failures, errors, timeouts)
    # We need to check all results, not just failures_to_analyze
    all_results = test_results.get('all_results', [])
    failures_to_analyze = test_results.get('failures_to_analyze', [])
    
    # If all_results is not provided, use failures_to_analyze
    results_to_check = all_results if all_results else failures_to_analyze
    
    num_5xx_errors = 0
    num_invalid_success = 0
    num_timeouts = 0
    
    for result in results_to_check:
        failure_reason = result.get('failure_reason', '') or ''
        status_code = result.get('status_code')
        result_type = result.get('result', '')
        
        # Count 5xx errors (server errors)
        if status_code and status_code >= 500:
            num_5xx_errors += 1
        elif '5xx' in failure_reason or 'Server Error' in failure_reason:
            num_5xx_errors += 1
        
        # Count invalid successes (bad input accepted)
        if 'Invalid success' in failure_reason or 'bad input was accepted' in failure_reason.lower():
            num_invalid_success += 1
        
        # Count timeouts
        if 'timeout' in failure_reason.lower() or result_type == 'timeout':
            num_timeouts += 1
    
    # Also check from test run summary if available
    if 'test_run' in test_results:
        test_run = test_results['test_run']
        # We can't directly count from summary, but we already counted from results
    
    # Apply penalties per spec
    score -= (5 * num_5xx_errors)
    score -= (3 * num_invalid_success)
    score -= (2 * num_timeouts)
    
    # Ensure bounds (0-100)
    score = max(0.0, min(100.0, score))
    
    return round(score, 2)