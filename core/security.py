from jose import jwt, JWTError
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from fastapi import HTTPException, status, Depends
from fastapi.security import APIKeyHeader
from passlib.context import CryptContext
from core import database, models
from core.config import settings
from schemas import token_schema
# from google import genai
from cryptography.fernet import Fernet
# from google.genai import types
import google.generativeai as genai
from google.api_core import exceptions



token_header = APIKeyHeader(name="Authorization", auto_error=False)

SECRET_KEY = settings.secret_key
ALGORITHM = settings.algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes


def create_access_token(data: dict):
    """
    Create a JWT access token with expiration.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_access_token(token: str, credentials_exception):
    """
    Verify the JWT token and return TokenData.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("user_id")
        if user_id is None:
            raise credentials_exception
        token_data = token_schema.TokenData(user_id=user_id)
    except JWTError:
        raise credentials_exception
    return token_data


def get_current_user(
    token: str = Depends(token_header),
    db: Session = Depends(database.get_db)
):
    """
    Get the currently authenticated user from the token (Bearer Token).
    """

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )

    if not token:
        raise credentials_exception

    # Token format must be: Bearer <token>
    if not token.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header format. Use: Bearer <token>"
        )

    # Extract real token
    token = token.split(" ")[1]

    # Verify token
    token_data = verify_access_token(token, credentials_exception)

    # Get user from DB
    user = db.query(models.User).filter(models.User.user_id == token_data.user_id).first()
    if not user:
        raise credentials_exception

    return user


pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def validate_gemini_key(api_key: str) -> bool:
    """
    Attempts to list models to verify if the API key is valid.
    Returns True if valid, False otherwise.
    """
    try:
        genai.configure(api_key=api_key)
        # Attempt a simple API call
        for model in genai.list_models():
            return True # If we can list models, the key is valid
    except exceptions.Unauthenticated:
        print("Error: The provided API key is invalid.")
        return False
    except exceptions.InvalidArgument:
        print("Error: Invalid arguments or poorly formatted key.")
        return False
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return False
        

fernet = Fernet(settings.FERNET_KEY.encode())

def encrypt_api_key(api_key: str) -> str:
    return fernet.encrypt(api_key.encode()).decode()

def decrypt_api_key(encrypted_key: str) -> str:
    return fernet.decrypt(encrypted_key.encode()).decode()