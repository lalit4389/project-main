"""
Custom exceptions for the application
"""

from fastapi import HTTPException


class AutoTraderException(HTTPException):
    """Base exception for AutoTrader application"""
    
    def __init__(self, status_code: int, detail: str):
        super().__init__(status_code=status_code, detail=detail)


class AuthenticationError(AutoTraderException):
    """Authentication related errors"""
    
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(status_code=401, detail=detail)


class AuthorizationError(AutoTraderException):
    """Authorization related errors"""
    
    def __init__(self, detail: str = "Not authorized"):
        super().__init__(status_code=403, detail=detail)


class ValidationError(AutoTraderException):
    """Validation related errors"""
    
    def __init__(self, detail: str = "Validation failed"):
        super().__init__(status_code=422, detail=detail)


class NotFoundError(AutoTraderException):
    """Resource not found errors"""
    
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(status_code=404, detail=detail)


class ConflictError(AutoTraderException):
    """Resource conflict errors"""
    
    def __init__(self, detail: str = "Resource conflict"):
        super().__init__(status_code=409, detail=detail)


class BrokerError(AutoTraderException):
    """Broker related errors"""
    
    def __init__(self, detail: str = "Broker operation failed"):
        super().__init__(status_code=500, detail=detail)


class EncryptionError(AutoTraderException):
    """Encryption/Decryption errors"""
    
    def __init__(self, detail: str = "Encryption operation failed"):
        super().__init__(status_code=500, detail=detail)