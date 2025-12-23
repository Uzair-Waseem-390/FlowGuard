from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from core.database import get_db
from core import models
from core import security
from schemas import token_schema, user_schema


router = APIRouter(tags=["Authentication"])


# {
#   "full_name": "Uzair Waseem",
#   "email": "uzair@gmail.com",
#   "password": "123",
#   "gemini_api_key": "123"
# }
@router.post("/signup/", status_code=status.HTTP_201_CREATED, response_model=user_schema.UserResponse)
def create_user(user: user_schema.UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(models.User).filter(models.User.email == user.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User with email {user.email} already exists"
        )
    # Hash the password before storing
    hashed_password = security.hash_password(user.password)
    validation_result = security.validate_gemini_key(user.gemini_api_key)
    if validation_result is not True:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gemini API key validation failed. Please check your API key."
        )
    # Encrypt the Gemini API key before storing
    encrypted_api_key = security.encrypt_api_key(user.gemini_api_key)
    new_user = models.User(
        full_name=user.full_name,
        email=user.email,
        password_hash=hashed_password,
        gemini_api_key=encrypted_api_key
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user




@router.post("/login", response_model=token_schema.Token)
async def login(user_credentials: user_schema.UserLogin, db: Session = Depends(get_db)):
    # Find user by email
    user = db.query(models.User).filter(models.User.email == user_credentials.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Credentials"
        )

    # Verify password
    if not security.verify_password(user_credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Credentials"
        )

    # Create JWT token with correct user_id
    access_token = security.create_access_token(data={"user_id": user.user_id})

    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=user_schema.UserResponse)
async def get_current_user_details(current_user: models.User = Depends(security.get_current_user)):
    return current_user


@router.post("/validate-gemini-key")
async def validate_gemini_key_endpoint(
    request: dict,
    db: Session = Depends(get_db)
):
    """
    Validate a Gemini API key before updating
    """
    gemini_api_key = request.get("gemini_api_key")
    if not gemini_api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gemini API key is required"
        )
    
    is_valid = security.validate_gemini_key(gemini_api_key)
    return {"valid": is_valid}


@router.put("/update-api-key")
async def update_api_key(
    request: dict,
    current_user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update user's Gemini API key
    """
    gemini_api_key = request.get("gemini_api_key")
    if not gemini_api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gemini API key is required"
        )
    
    # Validate the API key first
    is_valid = security.validate_gemini_key(gemini_api_key)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Gemini API key. Please check your API key."
        )
    
    # Encrypt and update the API key
    encrypted_api_key = security.encrypt_api_key(gemini_api_key)
    current_user.gemini_api_key = encrypted_api_key
    db.commit()
    db.refresh(current_user)
    
    return {"message": "API key updated successfully"}