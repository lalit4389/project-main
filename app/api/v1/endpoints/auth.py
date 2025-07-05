"""
Authentication endpoints
"""

import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.core.database import get_db, User, PendingRegistration, OTP, PasswordResetToken
from app.core.security import (
    verify_password, get_password_hash, create_access_token, verify_token
)
from app.core.exceptions import AuthenticationError, ValidationError, NotFoundError
from app.schemas.auth import (
    UserRegister, UserLogin, UserResponse, Token, OTPVerify, 
    ForgotPassword, ResetPassword, ResendOTP
)
from app.services.email_service import EmailService

router = APIRouter()
security = HTTPBearer()
logger = logging.getLogger(__name__)
email_service = EmailService()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current authenticated user"""
    token = credentials.credentials
    payload = verify_token(token)
    
    if payload is None:
        raise AuthenticationError("Invalid or expired token")
    
    user_id = payload.get("sub")
    if user_id is None:
        raise AuthenticationError("Invalid token payload")
    
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise AuthenticationError("User not found")
    
    return user

@router.post("/register", response_model=dict)
async def register(user_data: UserRegister, db: AsyncSession = Depends(get_db)):
    """Register a new user - Step 1: Store pending registration and send OTP"""
    
    logger.info(f"📝 Registration attempt for: {user_data.email}")
    
    # Validate input
    if not user_data.email and not user_data.mobile_number:
        raise ValidationError("Email or mobile number is required")
    
    if not user_data.password or not user_data.name:
        raise ValidationError("Password and name are required")
    
    # Check if user already exists
    if user_data.email:
        result = await db.execute(select(User).where(User.email == user_data.email.lower()))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="User already exists")
    
    # Determine identifier
    identifier = user_data.email.lower() if user_data.email else user_data.mobile_number
    
    # Hash password
    hashed_password = get_password_hash(user_data.password)
    
    # Clean up existing pending registrations
    await db.execute(delete(PendingRegistration).where(PendingRegistration.identifier == identifier))
    await db.execute(delete(OTP).where(OTP.identifier == identifier, OTP.purpose == 'registration'))
    
    # Store pending registration
    now = int(time.time())
    expires_at = now + (30 * 60)  # 30 minutes
    
    pending_reg = PendingRegistration(
        email=user_data.email.lower() if user_data.email else None,
        password=hashed_password,
        name=user_data.name,
        mobile_number=user_data.mobile_number,
        identifier=identifier,
        created_at=now,
        expires_at=expires_at
    )
    
    db.add(pending_reg)
    
    # Generate OTP
    otp_code = str(uuid.uuid4().int)[:6]  # 6-digit OTP
    otp_expires_at = now + (10 * 60)  # 10 minutes
    
    otp_type = 'email' if user_data.email else 'mobile'
    
    # Send OTP
    try:
        await email_service.send_otp(identifier, otp_code, otp_type)
        logger.info(f"✅ OTP sent to {identifier}")
    except Exception as e:
        logger.error(f"❌ Failed to send OTP: {e}")
        # Continue with registration even if email fails
    
    # Store OTP
    otp_record = OTP(
        identifier=identifier,
        type=otp_type,
        otp=otp_code,
        purpose='registration',
        expires_at=otp_expires_at,
        created_at=now
    )
    
    db.add(otp_record)
    await db.commit()
    
    logger.info(f"✅ Registration initiated for {identifier}")
    
    return {
        "message": "Registration initiated. Please verify OTP to complete account creation.",
        "identifier": identifier,
        "requiresOTP": True
    }

@router.post("/verify-otp", response_model=dict)
async def verify_otp(otp_data: OTPVerify, db: AsyncSession = Depends(get_db)):
    """Verify OTP - Step 2: Complete registration after OTP verification"""
    
    logger.info(f"🔐 OTP verification for: {otp_data.identifier}")
    
    now = int(time.time())
    
    # Find valid OTP
    result = await db.execute(
        select(OTP).where(
            OTP.identifier == otp_data.identifier,
            OTP.otp == otp_data.otp,
            OTP.purpose == 'registration',
            OTP.expires_at > now
        ).order_by(OTP.created_at.desc()).limit(1)
    )
    otp_record = result.scalar_one_or_none()
    
    if not otp_record:
        raise ValidationError("Invalid or expired OTP")
    
    # Get pending registration
    result = await db.execute(
        select(PendingRegistration).where(
            PendingRegistration.identifier == otp_data.identifier,
            PendingRegistration.expires_at > now
        ).order_by(PendingRegistration.created_at.desc()).limit(1)
    )
    pending_reg = result.scalar_one_or_none()
    
    if not pending_reg:
        raise ValidationError("Registration session expired. Please register again.")
    
    # Create user account
    user = User(
        email=pending_reg.email,
        password=pending_reg.password,
        name=pending_reg.name,
        mobile_number=pending_reg.mobile_number
    )
    
    db.add(user)
    
    # Clean up
    await db.execute(delete(OTP).where(OTP.id == otp_record.id))
    await db.execute(delete(PendingRegistration).where(PendingRegistration.identifier == otp_data.identifier))
    
    await db.commit()
    await db.refresh(user)
    
    logger.info(f"✅ Account created successfully for {otp_data.identifier}")
    
    return {
        "message": "Account created successfully! You can now login with your credentials.",
        "accountCreated": True,
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "mobile_number": user.mobile_number
        }
    }

@router.post("/resend-otp", response_model=dict)
async def resend_otp(resend_data: ResendOTP, db: AsyncSession = Depends(get_db)):
    """Resend OTP"""
    
    logger.info(f"🔄 Resending OTP for: {resend_data.identifier}")
    
    now = int(time.time())
    
    # Check pending registration
    result = await db.execute(
        select(PendingRegistration).where(
            PendingRegistration.identifier == resend_data.identifier,
            PendingRegistration.expires_at > now
        ).order_by(PendingRegistration.created_at.desc()).limit(1)
    )
    pending_reg = result.scalar_one_or_none()
    
    if not pending_reg:
        raise ValidationError("No pending registration found. Please register again.")
    
    # Clean up existing OTPs
    await db.execute(
        delete(OTP).where(
            OTP.identifier == resend_data.identifier,
            OTP.purpose == 'registration'
        )
    )
    
    # Generate new OTP
    otp_code = str(uuid.uuid4().int)[:6]
    otp_expires_at = now + (10 * 60)  # 10 minutes
    
    otp_type = 'email' if pending_reg.email else 'mobile'
    
    # Send OTP
    try:
        await email_service.send_otp(resend_data.identifier, otp_code, otp_type)
        logger.info(f"✅ OTP resent to {resend_data.identifier}")
    except Exception as e:
        logger.error(f"❌ Failed to resend OTP: {e}")
        raise HTTPException(status_code=500, detail="Failed to send OTP. Please try again.")
    
    # Store new OTP
    otp_record = OTP(
        identifier=resend_data.identifier,
        type=otp_type,
        otp=otp_code,
        purpose='registration',
        expires_at=otp_expires_at,
        created_at=now
    )
    
    db.add(otp_record)
    await db.commit()
    
    return {"message": "OTP resent successfully"}

@router.post("/login", response_model=Token)
async def login(user_data: UserLogin, db: AsyncSession = Depends(get_db)):
    """Login user"""
    
    logger.info(f"🔐 Login attempt for: {user_data.email}")
    
    # Find user
    result = await db.execute(select(User).where(User.email == user_data.email.lower()))
    user = result.scalar_one_or_none()
    
    if not user:
        logger.warning(f"❌ Login failed - User not found: {user_data.email}")
        raise HTTPException(
            status_code=404,
            detail="Account not available",
            headers={"message": "No account found with this email address. Please check your email or create a new account."}
        )
    
    # Verify password
    if not verify_password(user_data.password, user.password):
        logger.warning(f"❌ Login failed - Invalid password: {user_data.email}")
        raise HTTPException(
            status_code=401,
            detail="Invalid password",
            headers={"message": "The password you entered is incorrect. Please try again."}
        )
    
    # Create access token
    access_token = create_access_token(data={"sub": str(user.id)})
    
    logger.info(f"✅ Login successful for: {user_data.email}")
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "message": "Login successful",
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name
        }
    }

@router.post("/forgot-password", response_model=dict)
async def forgot_password(forgot_data: ForgotPassword, db: AsyncSession = Depends(get_db)):
    """Initiate password reset"""
    
    logger.info(f"🔑 Password reset request for: {forgot_data.identifier}")
    
    # Find user
    result = await db.execute(
        select(User).where(
            (User.email == forgot_data.identifier) | 
            (User.mobile_number == forgot_data.identifier)
        )
    )
    user = result.scalar_one_or_none()
    
    # Always return success for security
    if user:
        # Clean up existing OTPs
        await db.execute(
            delete(OTP).where(
                OTP.identifier == forgot_data.identifier,
                OTP.purpose == 'password_reset'
            )
        )
        
        # Generate OTP
        otp_code = str(uuid.uuid4().int)[:6]
        now = int(time.time())
        expires_at = now + (10 * 60)  # 10 minutes
        
        otp_type = 'email' if user.email == forgot_data.identifier else 'mobile'
        
        # Send OTP
        try:
            await email_service.send_password_reset_otp(forgot_data.identifier, otp_code)
            logger.info(f"✅ Password reset OTP sent to {forgot_data.identifier}")
        except Exception as e:
            logger.error(f"❌ Failed to send password reset OTP: {e}")
            raise HTTPException(status_code=500, detail="Failed to send OTP. Please try again.")
        
        # Store OTP
        otp_record = OTP(
            identifier=forgot_data.identifier,
            type=otp_type,
            otp=otp_code,
            purpose='password_reset',
            expires_at=expires_at,
            created_at=now
        )
        
        db.add(otp_record)
        await db.commit()
    else:
        logger.warning(f"❌ Password reset attempt for unknown identifier: {forgot_data.identifier}")
    
    return {"message": "If a matching account is found, an OTP has been sent."}

@router.post("/verify-otp-reset", response_model=dict)
async def verify_otp_reset(otp_data: OTPVerify, db: AsyncSession = Depends(get_db)):
    """Verify OTP for password reset"""
    
    logger.info(f"🔐 OTP verification for password reset: {otp_data.identifier}")
    
    now = int(time.time())
    
    # Find valid OTP
    result = await db.execute(
        select(OTP).where(
            OTP.identifier == otp_data.identifier,
            OTP.otp == otp_data.otp,
            OTP.purpose == 'password_reset',
            OTP.expires_at > now
        ).order_by(OTP.created_at.desc()).limit(1)
    )
    otp_record = result.scalar_one_or_none()
    
    if not otp_record:
        raise ValidationError("Invalid or expired OTP")
    
    # Generate reset token
    reset_token = str(uuid.uuid4())
    token_expires_at = now + (15 * 60)  # 15 minutes
    
    # Store reset token
    reset_token_record = PasswordResetToken(
        identifier=otp_data.identifier,
        token=reset_token,
        expires_at=token_expires_at,
        created_at=now
    )
    
    db.add(reset_token_record)
    
    # Delete used OTP
    await db.execute(delete(OTP).where(OTP.id == otp_record.id))
    
    await db.commit()
    
    logger.info(f"✅ OTP verified for password reset: {otp_data.identifier}")
    
    return {
        "message": "OTP verified successfully",
        "resetToken": reset_token
    }

@router.post("/reset-password", response_model=dict)
async def reset_password(reset_data: ResetPassword, db: AsyncSession = Depends(get_db)):
    """Reset password using reset token"""
    
    logger.info(f"🔑 Password reset with token")
    
    now = int(time.time())
    
    # Find valid reset token
    result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token == reset_data.resetToken,
            PasswordResetToken.expires_at > now
        ).order_by(PasswordResetToken.created_at.desc()).limit(1)
    )
    token_record = result.scalar_one_or_none()
    
    if not token_record:
        raise ValidationError("Invalid or expired reset token")
    
    # Hash new password
    hashed_password = get_password_hash(reset_data.newPassword)
    
    # Update user password
    result = await db.execute(
        select(User).where(
            (User.email == token_record.identifier) | 
            (User.mobile_number == token_record.identifier)
        )
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise NotFoundError("User not found")
    
    user.password = hashed_password
    user.updated_at = datetime.utcnow()
    
    # Delete reset token
    await db.execute(delete(PasswordResetToken).where(PasswordResetToken.id == token_record.id))
    
    await db.commit()
    
    logger.info(f"✅ Password reset successfully for: {token_record.identifier}")
    
    return {"message": "Password reset successfully"}

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return {
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "name": current_user.name,
            "mobile_number": current_user.mobile_number,
            "created_at": current_user.created_at
        }
    }