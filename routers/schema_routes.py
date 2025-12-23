from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional, List
import json
import yaml
import hashlib
import uuid
import tempfile
import os

from core.database import get_db
from core import models
from core import security
from schemas import schema_schemas, user_schema
from core.config import settings
import logging
logger = logging.getLogger(__name__)
from services.agent1_service import process_schema_with_agent1
from services.validation_service import ValidationService

router = APIRouter(
    tags=["Schema Management"]
)

def validate_schema_file_content(content: str, filename: str) -> dict:
    """
    Validate and parse schema file (JSON or YAML)
    Returns parsed schema dict if valid
    """
    import json
    import yaml
    
    try:
        if filename.lower().endswith('.json'):
            schema = json.loads(content)
        elif filename.lower().endswith(('.yaml', '.yml')):
            schema = yaml.safe_load(content)
        else:
            raise ValueError("Unsupported file format. Use .json, .yaml, or .yml")
        
        # Basic validation - must be a dictionary
        if not isinstance(schema, dict):
            raise ValueError("Schema must be a JSON object")
        
        return schema
        
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {str(e)}")
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML: {str(e)}")
    except Exception as e:
        raise ValueError(f"Error parsing schema: {str(e)}")
# def validate_schema_file_content(content: str, filename: str) -> dict:
#     """
#     Validate and parse schema file (JSON or YAML)
#     Returns parsed schema dict if valid
#     """
#     try:
#         if filename.lower().endswith('.json'):
#             return json.loads(content)
#         elif filename.lower().endswith(('.yaml', '.yml')):
#             return yaml.safe_load(content)
#         else:
#             raise ValueError("Unsupported file format. Use .json, .yaml, or .yml")
#     except json.JSONDecodeError as e:
#         raise ValueError(f"Invalid JSON: {str(e)}")
#     except yaml.YAMLError as e:
#         raise ValueError(f"Invalid YAML: {str(e)}")
#     except Exception as e:
#         raise ValueError(f"Error parsing schema: {str(e)}")


def calculate_schema_hash(schema_content: dict, base_url: str) -> str:
    """Use the validation service's hash function"""
    return ValidationService.calculate_schema_hash(schema_content, base_url)
# def calculate_schema_hash(schema_content: dict, base_url: str) -> str:
#     """
#     Calculate SHA256 hash of schema + base URL for caching
#     """
#     content_str = json.dumps(schema_content, sort_keys=True) + base_url
#     return hashlib.sha256(content_str.encode()).hexdigest()


@router.post("/upload", response_model=schema_schemas.SchemaUploadResponse)
async def upload_schema(
    base_url: str = Form(..., description="Base URL of the API to test"),
    schema_file: UploadFile = File(..., description="OpenAPI schema file (JSON/YAML)"),
    current_user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload API schema for testing.
    
    STRICT REQUIREMENTS (from FlowGuard spec):
    - Base URL is REQUIRED
    - Schema file is REQUIRED
    - Both must be provided, otherwise REJECT immediately
    - AI processing happens NOW (Agent 1)
    - Only clean, validated data is saved to DB
    """
    
    # 1. Validate inputs (per spec section 2)
    if not base_url or not base_url.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Base URL is required"
        )
    
    if not schema_file or schema_file.filename == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Schema file is required"
        )
    
    # Basic URL validation
    if not base_url.startswith(('http://', 'https://')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Base URL must start with http:// or https://"
        )
    
    # 2. Read and validate schema file
    try:
        content = await schema_file.read()
        content_str = content.decode('utf-8')
        
        # Validate file content
        parsed_schema = validate_schema_file_content(content_str, schema_file.filename)
        
        if not parsed_schema:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Schema file is empty"
            )
            
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid schema file: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading schema file: {str(e)}"
        )
    
    # 3. Check if schema already exists (caching - per spec section 6)
    schema_hash = calculate_schema_hash(parsed_schema, base_url)
    
    existing_schema = db.query(models.APISchema).filter(
        models.APISchema.schema_hash == schema_hash,
        models.APISchema.user_id == current_user.user_id
    ).first()
    
    if existing_schema:
        # Return existing schema - NO AI CALL NEEDED (cost optimization)
        return {
            "upload_id": str(uuid.uuid4()),
            "message": "Schema already exists in cache. Skipping AI processing.",
            "base_url": base_url,
            "filename": schema_file.filename,
            "file_size": len(content),
            "status": "cached",
            "schema_id": existing_schema.schema_id
        }
    
    # 4. CALL AGENT 1 IMMEDIATELY (per spec section 4)
    try:
        # Import services
        from services.agent1_service import process_schema_with_agent1
        from services.validation_service import ValidationService
        
        # Process with Agent 1 (Gemini 2.5 Flash)
        agent1_result = process_schema_with_agent1(
            raw_schema=parsed_schema,
            base_url=base_url,
            encrypted_gemini_key=current_user.gemini_api_key
        )
        
        # 5. CODE VALIDATION LAYER (per spec section 5 - NO AI)
        is_valid, validation_errors = ValidationService.validate_agent1_output(
            agent1_result.dict(),
            base_url
        )
        
        # Check if Agent 1 rejected or validation failed
        if agent1_result.status == 'reject' or not is_valid:
            # Combine all errors
            all_errors = []
            if agent1_result.errors:
                all_errors.extend(agent1_result.errors)
            if validation_errors:
                all_errors.extend(validation_errors)
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Schema validation failed",
                    "errors": all_errors
                }
            )
        
        # 6. SAVE CLEAN DATA TO DB (per spec section 6)
        new_schema = models.APISchema(
            user_id=current_user.user_id,
            original_filename=schema_file.filename,
            base_url=base_url,
            normalized_schema=agent1_result.normalized_schema,
            schema_hash=schema_hash,
            test_cases=agent1_result.test_cases
        )
        
        db.add(new_schema)
        db.commit()
        db.refresh(new_schema)
        
        # Track that Agent 1 was used for this schema
        # (Important for cost tracking)
        
        return {
            "upload_id": str(uuid.uuid4()),
            "message": "Schema processed and saved successfully",
            "base_url": base_url,
            "filename": schema_file.filename,
            "file_size": len(content),
            "status": "processed",
            "schema_id": new_schema.schema_id
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Handle any other errors
        logger.error(f"Failed to process schema: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process schema: {str(e)}"
        )

# @router.post("/upload", response_model=schema_schemas.SchemaUploadResponse)
# async def upload_schema(
#     base_url: str = Form(..., description="Base URL of the API to test"),
#     schema_file: UploadFile = File(..., description="OpenAPI schema file (JSON/YAML)"),
#     current_user: models.User = Depends(security.get_current_user),
#     db: Session = Depends(get_db)
# ):
#     """
#     Upload API schema for testing.
    
#     STRICT REQUIREMENTS (from FlowGuard spec):
#     - Base URL is REQUIRED
#     - Schema file is REQUIRED
#     - Both must be provided, otherwise REJECT immediately
#     - No AI calls at this stage
#     """
    
#     # 1. Validate inputs (per spec section 2)
#     if not base_url or not base_url.strip():
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Base URL is required"
#         )
    
#     if not schema_file or schema_file.filename == "":
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Schema file is required"
#         )
    
#     # Basic URL validation
#     if not base_url.startswith(('http://', 'https://')):
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Base URL must start with http:// or https://"
#         )
    
#     # 2. Read and validate schema file
#     try:
#         content = await schema_file.read()
#         content_str = content.decode('utf-8')
        
#         # Validate file content
#         parsed_schema = validate_schema_file_content(content_str, schema_file.filename)
        
#         if not parsed_schema:
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="Schema file is empty"
#             )
            
#     except ValueError as e:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail=f"Invalid schema file: {str(e)}"
#         )
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Error reading schema file: {str(e)}"
#         )
    
#     # 3. Check if schema already exists (caching - per spec section 6)
#     schema_hash = calculate_schema_hash(parsed_schema, base_url)
    
#     existing_schema = db.query(models.APISchema).filter(
#         models.APISchema.schema_hash == schema_hash,
#         models.APISchema.user_id == current_user.user_id
#     ).first()
    
#     if existing_schema:
#         # Return existing schema - NO AI CALL NEEDED (cost optimization)
#         return JSONResponse(
#             status_code=status.HTTP_200_OK,
#             content={
#                 "upload_id": str(uuid.uuid4()),
#                 "message": "Schema already exists in cache. Skipping AI processing.",
#                 "base_url": base_url,
#                 "filename": schema_file.filename,
#                 "file_size": len(content),
#                 "status": "cached",
#                 "schema_id": existing_schema.schema_id,
#                 "schema_hash": schema_hash
#             }
#         )
    
#     # 4. Store in temporary location for Agent 1 processing
#     # In production, you might use Redis or a task queue
#     # For now, we'll create a temporary record
#     upload_id = str(uuid.uuid4())
    
#     # Create a temporary file (in production, use proper job queue)
#     temp_dir = tempfile.gettempdir()
#     temp_filepath = os.path.join(temp_dir, f"flowguard_{upload_id}_{schema_file.filename}")
    
#     with open(temp_filepath, 'w', encoding='utf-8') as f:
#         json.dump({
#             "raw_schema": parsed_schema,
#             "base_url": base_url,
#             "filename": schema_file.filename,
#             "user_id": current_user.user_id,
#             "upload_id": upload_id
#         }, f)
    
#     # 5. Return success response
#     return {
#         "upload_id": upload_id,
#         "message": "Schema uploaded successfully. Ready for AI processing.",
#         "base_url": base_url,
#         "filename": schema_file.filename,
#         "file_size": len(content),
#         "status": "uploaded"
#     }

@router.get("/my-schemas", response_model=List[schema_schemas.APISchemaResponse])
async def get_my_schemas(
    current_user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all schemas uploaded by the current user
    """
    schemas = db.query(models.APISchema).filter(
        models.APISchema.user_id == current_user.user_id
    ).order_by(models.APISchema.created_at.desc()).all()
    
    # Format response with additional info
    response = []
    for schema in schemas:
        # Calculate endpoints and test cases from normalized schema
        total_endpoints = 0
        total_test_cases = 0
        
        if schema.normalized_schema:
            total_endpoints = len(schema.normalized_schema)
        
        if schema.test_cases:
            total_test_cases = len(schema.test_cases)
        
        response.append({
            "schema_id": schema.schema_id,
            "base_url": schema.base_url,
            "original_filename": schema.original_filename,
            "schema_hash": schema.schema_hash,
            "total_endpoints": total_endpoints,
            "total_test_cases": total_test_cases,
            "created_at": schema.created_at
        })
    
    return response

@router.get("/{schema_id}")
async def get_schema_details(
    schema_id: int,
    current_user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get details of a specific schema
    """
    schema = db.query(models.APISchema).filter(
        models.APISchema.schema_id == schema_id,
        models.APISchema.user_id == current_user.user_id
    ).first()
    
    if not schema:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schema not found"
        )
    
    return schema


@router.post("/{schema_id}/run-tests")
async def run_tests(
    schema_id: int,
    current_user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Execute test cases for a schema
    Returns test run results
    """
    # Check if schema exists and belongs to user
    schema = db.query(models.APISchema).filter(
        models.APISchema.schema_id == schema_id,
        models.APISchema.user_id == current_user.user_id
    ).first()
    
    if not schema:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schema not found"
        )
    
    # Check if there are test cases
    if not schema.test_cases or len(schema.test_cases) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No test cases available for this schema"
        )
    
    try:
        # Run the test suite
        from services.test_executor import run_test_suite
        results = await run_test_suite(schema_id, db, current_user)
        
        # Calculate stability score
        from services.stability_score import calculate_stability_score
        stability_score = calculate_stability_score(results)
        
        # Update test run with score
        test_run = results['test_run']
        test_run.stability_score = stability_score
        db.commit()
        
        return {
            "run_id": results['run_id'],
            "schema_id": schema_id,
            "total_tests": results['total_tests'],
            "passed": results['passed'],
            "failed": results['failed'],
            "errors": results['errors'],
            "stability_score": stability_score,
            "message": f"Test execution completed. {results['failed']} failures detected.",
            "has_failures": results['failed'] > 0 or results['errors'] > 0
        }
        
    except Exception as e:
        logger.error(f"Test execution failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Test execution failed: {str(e)}"
        )

@router.get("/{schema_id}/test-runs")
async def get_test_runs(
    schema_id: int,
    current_user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all test runs for a schema
    """
    # Verify schema ownership
    schema = db.query(models.APISchema).filter(
        models.APISchema.schema_id == schema_id,
        models.APISchema.user_id == current_user.user_id
    ).first()
    
    if not schema:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schema not found"
        )
    
    # Get test runs
    test_runs = db.query(models.TestRun).filter(
        models.TestRun.schema_id == schema_id
    ).order_by(models.TestRun.started_at.desc()).all()
    
    return test_runs

@router.get("/test-runs/{run_id}")
async def get_test_run_details(
    run_id: int,
    current_user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed results for a test run
    """
    test_run = db.query(models.TestRun).filter(
        models.TestRun.run_id == run_id,
        models.TestRun.user_id == current_user.user_id
    ).first()
    
    if not test_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test run not found"
        )
    
    # Get failures
    failures = db.query(models.TestFailure).filter(
        models.TestFailure.run_id == run_id
    ).all()
    
    return {
        "test_run": test_run,
        "failures": failures
    }
    

@router.post("/test-runs/{run_id}/analyze-failures")
async def analyze_failures(
    run_id: int,
    current_user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Analyze failures using Agent 2 (Gemini 2.5 Lite)
    Only runs if failures exist (cost optimization)
    """
    # Check if test run exists and belongs to user
    test_run = db.query(models.TestRun).filter(
        models.TestRun.run_id == run_id,
        models.TestRun.user_id == current_user.user_id
    ).first()
    
    if not test_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test run not found"
        )
    
    # Check if there are failures to analyze
    failure_count = db.query(models.TestFailure).filter(
        models.TestFailure.run_id == run_id
    ).count()
    
    if failure_count == 0:
        return {
            "message": "No failures to analyze",
            "run_id": run_id,
            "agent2_called": False
        }
    
    # Check if Agent 2 was already called (idempotent)
    if test_run.agent2_called:
        # Return existing analysis
        failures = db.query(models.TestFailure).filter(
            models.TestFailure.run_id == run_id
        ).all()
        
        analyses = []
        for failure in failures:
            analyses.append({
                "endpoint": failure.endpoint,
                "test_type": failure.test_type,
                "root_cause": failure.root_cause,
                "risk_level": failure.risk_level,
                "fix_suggestion": failure.fix_suggestion
            })
        
        return {
            "message": "Using cached analysis",
            "run_id": run_id,
            "analyzed_count": len(analyses),
            "agent2_called": True,
            "analyses": analyses
        }
    
    try:
        # Call Agent 2 service
        from services.agent2_service import analyze_failures_with_agent2
        
        result = await analyze_failures_with_agent2(
            run_id=run_id,
            encrypted_gemini_key=current_user.gemini_api_key,
            db=db
        )
        
        return {
            "message": "Failures analyzed successfully",
            "run_id": run_id,
            "agent2_called": True,
            **result
        }
        
    except Exception as e:
        logger.error(f"Failure analysis failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failure analysis failed: {str(e)}"
        )

@router.get("/test-runs/{run_id}/final-report")
async def get_final_report(
    run_id: int,
    current_user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate final report for a test run
    Includes stability score and failure analysis
    Per FlowGuard spec section 11
    """
    # Get test run
    test_run = db.query(models.TestRun).filter(
        models.TestRun.run_id == run_id,
        models.TestRun.user_id == current_user.user_id
    ).first()
    
    if not test_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test run not found"
        )
    
    # Get schema info
    schema = db.query(models.APISchema).filter(
        models.APISchema.schema_id == test_run.schema_id
    ).first()
    
    # Get failures with analysis
    failures = db.query(models.TestFailure).filter(
        models.TestFailure.run_id == run_id
    ).all()
    
    # Prepare failure explanations
    failure_explanations = []
    for failure in failures:
        failure_explanations.append({
            "endpoint": failure.endpoint,
            "http_method": failure.http_method,
            "test_type": failure.test_type,
            "status_code": failure.status_code,
            "failure_reason": failure.failure_reason,
            "root_cause": failure.root_cause or "Not analyzed yet",
            "risk_level": failure.risk_level or "medium",
            "fix_suggestion": failure.fix_suggestion or "Run failure analysis first"
        })
    
    # Calculate endpoints tested (from normalized schema)
    endpoints_tested = 0
    if schema and schema.normalized_schema:
        endpoints_tested = len(schema.normalized_schema)
    
    # Prepare report
    report = {
        "test_run_id": test_run.run_id,
        "schema_id": test_run.schema_id,
        "base_url": schema.base_url if schema else "Unknown",
        "execution_date": test_run.started_at.isoformat(),
        "summary": {
            "endpoints_tested": endpoints_tested,
            "total_tests": test_run.total_tests,
            "passed_tests": test_run.passed_tests,
            "failed_tests": test_run.failed_tests,
            "error_tests": test_run.error_tests,
            "total_failures": len(failures)
        },
        "stability_score": test_run.stability_score or 0.0,
        "ai_usage": {
            "agent1_called": test_run.agent1_called,
            "agent2_called": test_run.agent2_called
        },
        "failures": failure_explanations,
        "recommendations": []
    }
    
    # Add overall recommendations based on stability score
    if test_run.stability_score is not None:
        if test_run.stability_score >= 90:
            report["overall_health"] = "EXCELLENT"
            report["recommendations"].append("API is very stable. Consider adding more edge case tests.")
        elif test_run.stability_score >= 70:
            report["overall_health"] = "GOOD"
            report["recommendations"].append("API is generally stable. Address the critical issues first.")
        elif test_run.stability_score >= 50:
            report["overall_health"] = "FAIR"
            report["recommendations"].append("API needs improvement. Focus on high-risk failures.")
        else:
            report["overall_health"] = "POOR"
            report["recommendations"].append("API is unstable. Immediate action required on critical issues.")
    
    # Add recommendation to run Agent 2 if not run yet
    if failures and not test_run.agent2_called:
        report["recommendations"].append("Run failure analysis to get AI-powered root cause and fix suggestions.")
    
    return report

@router.post("/{schema_id}/complete-test-flow")
async def complete_test_flow(
    schema_id: int,
    current_user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Complete FlowGuard test flow in one call:
    1. Run tests (if not already run)
    2. Analyze failures (if any)
    3. Generate final report
    
    This is the main user-facing endpoint.
    """
    # 1. Check schema exists
    schema = db.query(models.APISchema).filter(
        models.APISchema.schema_id == schema_id,
        models.APISchema.user_id == current_user.user_id
    ).first()
    
    if not schema:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schema not found"
        )
    
    # 2. Check for existing recent test run (last 1 hour)
    from datetime import datetime, timedelta
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    
    existing_run = db.query(models.TestRun).filter(
        models.TestRun.schema_id == schema_id,
        models.TestRun.user_id == current_user.user_id,
        models.TestRun.started_at > one_hour_ago,
        models.TestRun.status == models.TestStatus.COMPLETED
    ).order_by(models.TestRun.started_at.desc()).first()
    
    run_id = None
    
    if existing_run:
        # Use existing test run
        run_id = existing_run.run_id
        message = "Using recent test run"
    else:
        # 3. Run tests
        try:
            from services.test_executor import run_test_suite
            from services.stability_score import calculate_stability_score
            
            results = await run_test_suite(schema_id, db, current_user)
            run_id = results['run_id']
            
            # Calculate and update stability score
            stability_score = calculate_stability_score(results)
            test_run = results['test_run']
            test_run.stability_score = stability_score
            db.commit()
            
            message = "Tests executed successfully"
            
        except Exception as e:
            logger.error(f"Test execution failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Test execution failed: {str(e)}"
            )
    
    # 4. Analyze failures if any exist
    if run_id:
        test_run = db.query(models.TestRun).filter(
            models.TestRun.run_id == run_id
        ).first()
        
        if test_run.failed_tests > 0 and not test_run.agent2_called:
            try:
                from services.agent2_service import analyze_failures_with_agent2
                await analyze_failures_with_agent2(
                    run_id=run_id,
                    encrypted_gemini_key=current_user.gemini_api_key,
                    db=db
                )
            except Exception as e:
                logger.warning(f"Failed to analyze failures: {e}")
                # Continue anyway - Agent 2 failure shouldn't block report
    
        # 5. Generate final report
        if run_id:
            # Re-fetch to get updated data
            test_run = db.query(models.TestRun).filter(
                models.TestRun.run_id == run_id
            ).first()
            
            # Get the final report (call the function directly to avoid circular import)
            report_response = await get_final_report(run_id, current_user, db)
        
        return {
            "success": True,
            "message": message,
            "run_id": run_id,
            "report": report_response
        }
    
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Failed to complete test flow"
    )