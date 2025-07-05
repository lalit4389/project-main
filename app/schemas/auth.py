"""
Authentication schemas
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, validator


class UserRegister(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    mobile_number: Optional[str] = None
    password: str
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters long')
        return v
    
    @validator('name')
    def validate_name(cls, v):
        if len(v.strip()) < 2:
            raise ValueError('Name must be at least 2 characters long')
        return v.strip()


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class OTPVerify(BaseModel):
    identifier: str
    otp: str
    
    @validator('otp')
    def validate_otp(cls, v):
        if not v.isdigit() or len(v) != 6:
            raise ValueError('OTP must be 6 digits')
        return v


class ResendOTP(BaseModel):
    identifier: str


class ForgotPassword(BaseModel):
    identifier: str


class ResetPassword(BaseModel):
    resetToken: str
    newPassword: str
    
    @validator('newPassword')
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters long')
        return v


class Token(BaseModel):
    access_token: str
    token_type: str
    message: str
    user: dict


class UserResponse(BaseModel):
    user: dict