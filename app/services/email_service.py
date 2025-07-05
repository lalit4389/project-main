"""
Email service for sending OTPs and notifications
"""

import asyncio
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Email service for sending OTPs and notifications"""
    
    def __init__(self):
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_username = settings.SMTP_USERNAME
        self.smtp_password = settings.SMTP_PASSWORD
        self.email_from = settings.EMAIL_FROM
        self.is_ready = False
        
        # Test email service on initialization
        asyncio.create_task(self._test_connection())
    
    async def _test_connection(self):
        """Test SMTP connection"""
        try:
            server = smtplib.SMTP(self.smtp_host, self.smtp_port)
            server.starttls()
            server.login(self.smtp_username, self.smtp_password)
            server.quit()
            
            self.is_ready = True
            logger.info("✅ Email service is ready")
        except Exception as e:
            logger.warning(f"⚠️ Email service configuration warning: {e}")
            logger.warning("📧 Email functionality will be simulated in console logs")
            self.is_ready = False
    
    async def send_otp(self, identifier: str, otp: str, otp_type: str = 'email') -> dict:
        """Send OTP to user"""
        try:
            logger.info(f"📧 Attempting to send OTP to {identifier} (type: {otp_type})")
            
            if otp_type == 'email':
                if not self.is_ready:
                    # Simulate email sending
                    logger.info(f"📧 [EMAIL SIMULATION] Sending OTP email to: {identifier}")
                    logger.info(f"📧 [EMAIL SIMULATION] OTP Code: {otp}")
                    logger.info("📧 [EMAIL SIMULATION] Subject: AutoTraderHub - Email Verification Code")
                    
                    return {
                        "success": True,
                        "messageId": f"simulated_email_{int(asyncio.get_event_loop().time())}",
                        "message": "OTP email sent successfully (simulated - check console for details)",
                        "simulated": True
                    }
                
                # Send actual email
                subject = "AutoTraderHub - Email Verification Code"
                html_content = self._get_otp_email_template(otp)
                
                await self._send_email(identifier, subject, html_content)
                
                logger.info(f"✅ Registration OTP email sent to {identifier}")
                logger.info(f"🔐 OTP Code: {otp}")
                
                return {
                    "success": True,
                    "messageId": f"email_{int(asyncio.get_event_loop().time())}",
                    "message": "OTP sent successfully"
                }
            else:
                # SMS simulation
                logger.info(f"📱 [SMS SERVICE] Sending OTP to {identifier}")
                logger.info(f"📱 OTP Code: {otp}")
                logger.info(f"📱 Message: Your AutoTraderHub verification code is: {otp}. This code will expire in 10 minutes.")
                
                return {
                    "success": True,
                    "messageId": f"sms_{int(asyncio.get_event_loop().time())}",
                    "message": "SMS OTP sent successfully (simulated)"
                }
                
        except Exception as e:
            logger.error(f"❌ Failed to send OTP: {e}")
            
            # Fallback simulation
            logger.info(f"📧 [EMAIL SIMULATION - FALLBACK] Sending OTP to: {identifier}")
            logger.info(f"📧 [EMAIL SIMULATION - FALLBACK] OTP Code: {otp}")
            
            return {
                "success": True,
                "messageId": f"fallback_simulation_{int(asyncio.get_event_loop().time())}",
                "message": "OTP sent successfully (simulated due to SMTP error)",
                "simulated": True,
                "fallback": True
            }
    
    async def send_password_reset_otp(self, identifier: str, otp: str) -> dict:
        """Send password reset OTP"""
        try:
            logger.info(f"🔐 Attempting to send password reset OTP to {identifier}")
            
            if not self.is_ready:
                # Simulate email sending
                logger.info(f"🔐 [EMAIL SIMULATION] Sending password reset OTP to: {identifier}")
                logger.info(f"🔐 [EMAIL SIMULATION] OTP Code: {otp}")
                logger.info("🔐 [EMAIL SIMULATION] Subject: AutoTraderHub - Password Reset Code")
                
                return {
                    "success": True,
                    "messageId": f"simulated_reset_{int(asyncio.get_event_loop().time())}",
                    "message": "Password reset OTP sent successfully (simulated - check console for details)",
                    "simulated": True
                }
            
            # Send actual email
            subject = "AutoTraderHub - Password Reset Code"
            html_content = self._get_password_reset_email_template(otp)
            
            await self._send_email(identifier, subject, html_content)
            
            logger.info(f"✅ Password reset OTP email sent to {identifier}")
            logger.info(f"🔐 OTP Code: {otp}")
            
            return {
                "success": True,
                "messageId": f"reset_{int(asyncio.get_event_loop().time())}",
                "message": "Password reset OTP sent successfully"
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to send password reset OTP: {e}")
            
            # Fallback simulation
            logger.info(f"🔐 [EMAIL SIMULATION - FALLBACK] Sending password reset OTP to: {identifier}")
            logger.info(f"🔐 [EMAIL SIMULATION - FALLBACK] OTP Code: {otp}")
            
            return {
                "success": True,
                "messageId": f"fallback_reset_simulation_{int(asyncio.get_event_loop().time())}",
                "message": "Password reset OTP sent successfully (simulated due to SMTP error)",
                "simulated": True,
                "fallback": True
            }
    
    async def _send_email(self, to_email: str, subject: str, html_content: str):
        """Send email using SMTP"""
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"AutoTraderHub <{self.email_from}>"
        msg['To'] = to_email
        
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)
        
        # Send email in thread to avoid blocking
        def send_sync():
            server = smtplib.SMTP(self.smtp_host, self.smtp_port)
            server.starttls()
            server.login(self.smtp_username, self.smtp_password)
            server.send_message(msg)
            server.quit()
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, send_sync)
    
    def _get_otp_email_template(self, otp: str) -> str:
        """Get OTP email template"""
        return f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f8f9fa;">
            <div style="background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); padding: 30px; border-radius: 15px; text-align: center; margin-bottom: 20px;">
                <h1 style="color: white; margin: 0; font-size: 28px;">📈 AutoTraderHub</h1>
                <p style="color: #fef3c7; margin: 10px 0 0 0; font-size: 16px;">Automated Trading Platform</p>
            </div>
            
            <div style="background: white; padding: 30px; border-radius: 15px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
                <h2 style="color: #333; margin-bottom: 20px; text-align: center;">Email Verification Required</h2>
                
                <p style="color: #666; font-size: 16px; line-height: 1.6; margin-bottom: 25px;">
                    Thank you for registering with AutoTraderHub! To complete your account setup, please verify your email address using the code below:
                </p>
                
                <div style="background: #f8f9fa; border: 2px dashed #f59e0b; border-radius: 10px; padding: 25px; text-align: center; margin: 25px 0;">
                    <p style="color: #666; margin: 0 0 10px 0; font-size: 14px;">Your verification code is:</p>
                    <h1 style="color: #f59e0b; font-size: 36px; font-weight: bold; margin: 0; letter-spacing: 5px; font-family: 'Courier New', monospace;">{otp}</h1>
                </div>
                
                <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0; border-radius: 5px;">
                    <p style="color: #856404; margin: 0; font-size: 14px;">
                        ⚠️ <strong>Important:</strong> This code will expire in 10 minutes for security reasons.
                    </p>
                </div>
                
                <p style="color: #666; font-size: 14px; line-height: 1.6; margin-bottom: 20px;">
                    If you didn't create an account with AutoTraderHub, please ignore this email or contact our support team.
                </p>
                
                <div style="text-align: center; margin-top: 30px;">
                    <p style="color: #999; font-size: 12px; margin: 0;">
                        This is an automated message from AutoTraderHub. Please do not reply to this email.
                    </p>
                </div>
            </div>
            
            <div style="text-align: center; margin-top: 20px;">
                <p style="color: #999; font-size: 12px; margin: 0;">
                    © 2024 AutoTraderHub. All rights reserved.
                </p>
            </div>
        </div>
        """
    
    def _get_password_reset_email_template(self, otp: str) -> str:
        """Get password reset email template"""
        return f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f8f9fa;">
            <div style="background: linear-gradient(135deg, #dc3545 0%, #c82333 100%); padding: 30px; border-radius: 15px; text-align: center; margin-bottom: 20px;">
                <h1 style="color: white; margin: 0; font-size: 28px;">🔒 AutoTraderHub</h1>
                <p style="color: #f8d7da; margin: 10px 0 0 0; font-size: 16px;">Password Reset Request</p>
            </div>
            
            <div style="background: white; padding: 30px; border-radius: 15px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
                <h2 style="color: #333; margin-bottom: 20px; text-align: center;">Password Reset Verification</h2>
                
                <p style="color: #666; font-size: 16px; line-height: 1.6; margin-bottom: 25px;">
                    We received a request to reset your AutoTraderHub account password. If you made this request, please use the verification code below:
                </p>
                
                <div style="background: #f8f9fa; border: 2px dashed #dc3545; border-radius: 10px; padding: 25px; text-align: center; margin: 25px 0;">
                    <p style="color: #666; margin: 0 0 10px 0; font-size: 14px;">Your password reset code is:</p>
                    <h1 style="color: #dc3545; font-size: 36px; font-weight: bold; margin: 0; letter-spacing: 5px; font-family: 'Courier New', monospace;">{otp}</h1>
                </div>
                
                <div style="background: #f8d7da; border-left: 4px solid #dc3545; padding: 15px; margin: 20px 0; border-radius: 5px;">
                    <p style="color: #721c24; margin: 0; font-size: 14px;">
                        🚨 <strong>Security Notice:</strong> This code will expire in 10 minutes. If you didn't request this reset, please secure your account immediately.
                    </p>
                </div>
                
                <div style="background: #d1ecf1; border-left: 4px solid #17a2b8; padding: 15px; margin: 20px 0; border-radius: 5px;">
                    <p style="color: #0c5460; margin: 0; font-size: 14px;">
                        💡 <strong>Next Steps:</strong> After entering this code, you'll be able to set a new password for your account.
                    </p>
                </div>
                
                <p style="color: #666; font-size: 14px; line-height: 1.6; margin-bottom: 20px;">
                    If you didn't request a password reset, please ignore this email and consider changing your password as a precaution.
                </p>
                
                <div style="text-align: center; margin-top: 30px;">
                    <p style="color: #999; font-size: 12px; margin: 0;">
                        This is an automated security message from AutoTraderHub. Please do not reply to this email.
                    </p>
                </div>
            </div>
            
            <div style="text-align: center; margin-top: 20px;">
                <p style="color: #999; font-size: 12px; margin: 0;">
                    © 2024 AutoTraderHub. All rights reserved.
                </p>
            </div>
        </div>
        """