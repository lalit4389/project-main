"""
Security utilities for authentication and encryption
"""

import os
import time
from datetime import datetime, timedelta
from typing import Optional, Union

import bcrypt
from cryptography.fernet import Fernet
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Encryption setup
def get_encryption_key() -> bytes:
    """Get or generate encryption key"""
    key = settings.ENCRYPTION_KEY.encode()
    if len(key) < 32:
        key = key.ljust(32, b'0')
    elif len(key) > 32:
        key = key[:32]
    return Fernet.generate_key() if len(key) != 44 else key

# Initialize Fernet cipher
try:
    fernet = Fernet(get_encryption_key())
except Exception:
    # Fallback: generate a proper key
    fernet = Fernet(Fernet.generate_key())

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Optional[dict]:
    """Verify JWT token and return payload"""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None

def encrypt_data(data: str) -> str:
    """Encrypt sensitive data"""
    if not data:
        raise ValueError("Data to encrypt cannot be empty")
    
    try:
        encrypted_data = fernet.encrypt(data.encode())
        return encrypted_data.decode()
    except Exception as e:
        raise ValueError(f"Encryption failed: {str(e)}")

def decrypt_data(encrypted_data: str) -> str:
    """Decrypt sensitive data"""
    if not encrypted_data:
        raise ValueError("Encrypted data cannot be empty")
    
    try:
        decrypted_data = fernet.decrypt(encrypted_data.encode())
        return decrypted_data.decode()
    except Exception as e:
        raise ValueError(f"Decryption failed: {str(e)}")

def test_encryption() -> bool:
    """Test encryption/decryption functionality"""
    try:
        test_data = "test-api-key-12345"
        encrypted = encrypt_data(test_data)
        decrypted = decrypt_data(encrypted)
        
        if test_data == decrypted:
            print("✅ Encryption/Decryption test passed")
            return True
        else:
            print("❌ Test failed: Decrypted value mismatch")
            return False
    except Exception as e:
        print(f"❌ Encryption test error: {str(e)}")
        return False

# Test encryption on import
test_encryption()