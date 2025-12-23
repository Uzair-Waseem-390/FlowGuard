from pydantic import BaseModel, HttpUrl, field_validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

# Request schemas
class SchemaUploadRequest(BaseModel):
    base_url: str
    # Note: File will come as FormData, not JSON
    
    @field_validator('base_url')
    def validate_base_url(cls, v):
        if not v or v.strip() == "":
            raise ValueError("Base URL is required")
        # Basic URL validation
        if not v.startswith(('http://', 'https://')):
            raise ValueError("Base URL must start with http:// or https://")
        return v.strip()

class SchemaUploadResponse(BaseModel):
    upload_id: str  # Temporary ID before AI processing
    message: str
    base_url: str
    filename: str
    file_size: int
    status: str  # "uploaded", "processing", "rejected"

# Response schemas for Agent 1 output
# class Agent1Output(BaseModel):
#     status: str  # "ok" or "reject"
#     normalized_schema: Optional[List[Dict[str, Any]]] = None
#     test_cases: Optional[List[Dict[str, Any]]] = None
#     errors: Optional[List[str]] = None

# For database responses
class APISchemaResponse(BaseModel):
    schema_id: int
    base_url: str
    original_filename: str
    schema_hash: str
    total_endpoints: int
    total_test_cases: int
    created_at: datetime
    
    class Config:
        from_attributes = True
        
class Agent1Output(BaseModel):
    status: str  # "ok" or "reject"
    normalized_schema: Optional[List[Dict[str, Any]]] = None
    test_cases: Optional[List[Dict[str, Any]]] = None
    errors: Optional[List[str]] = None
    
    @field_validator('status')
    def validate_status(cls, v):
        if v not in ['ok', 'reject']:
            raise ValueError('status must be "ok" or "reject"')
        return v