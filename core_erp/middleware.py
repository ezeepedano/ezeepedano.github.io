"""
Security Middleware for ERP System

Provides security enhancements including:
- Security headers (HSTS, X-Frame-Options, etc.)
- Request logging
- IP-based access control (optional)
- Rate limiting helpers

Author: ERP Development Team
Created: 2026-02-04
"""

import logging
from typing import Callable, Optional
from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin


logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Add security headers to all responses.
    
    Implements OWASP recommended security headers:
    - X-Frame-Options: Prevents clickjacking
    - X-Content-Type-Options: Prevents MIME-sniffing
    - X-XSS-Protection: Enables XSS protection
    - Referrer-Policy: Controls referrer information
    - Permissions-Policy: Controls browser features
    """
    
    def process_response(
        self, 
        request: HttpRequest, 
        response: HttpResponse
    ) -> HttpResponse:
        """
        Add security headers to response.
        
        Args:
            request: HTTP request object
            response: HTTP response object
            
        Returns:
            Modified HTTP response with security headers
        """
        # Prevent clickjacking
        response['X-Frame-Options'] = 'DENY'
        
        # Prevent MIME-sniffing
        response['X-Content-Type-Options'] = 'nosniff'
        
        # Enable XSS protection
        response['X-XSS-Protection'] = '1; mode=block'
        
        # Control referrer information
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Control browser features (modern approach)
        response['Permissions-Policy'] = (
            'geolocation=(), microphone=(), camera=()'
        )
        
        # Content Security Policy (basic - customize as needed)
        if not response.get('Content-Security-Policy'):
            response['Content-Security-Policy'] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self' data:;"
            )
        
        return response


class RequestLoggingMiddleware(MiddlewareMixin):
    """
    Log all incoming requests for security auditing.
    
    Logs:
    - Request method and path
    - User information (if authenticated)
    - IP address
    - User agent
    - Response status code
    """
    
    def process_request(self, request: HttpRequest) -> None:
        """
        Log incoming request details.
        
        Args:
            request: HTTP request object
        """
        # Get client IP
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', 'Unknown')
        
        # Get user agent
        user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
        
        # Get user info
        user_info = 'Anonymous'
        if request.user.is_authenticated:
            user_info = f"User:{request.user.username} (ID:{request.user.id})"
        
        logger.info(
            f"REQUEST: {request.method} {request.path} | "
            f"{user_info} | IP:{ip} | UA:{user_agent[:50]}"
        )
    
    def process_response(
        self, 
        request: HttpRequest, 
        response: HttpResponse
    ) -> HttpResponse:
        """
        Log response status.
        
        Args:
            request: HTTP request object
            response: HTTP response object
            
        Returns:
            Unmodified HTTP response
        """
        logger.info(
            f"RESPONSE: {request.method} {request.path} | "
            f"Status:{response.status_code}"
        )
        return response


class IPWhitelistMiddleware(MiddlewareMixin):
    """
    Optional IP-based access control.
    
    Configure ALLOWED_IPS in settings.py to enable.
    Example: ALLOWED_IPS = ['127.0.0.1', '192.168.1.0/24']
    """
    
    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """
        Check if request IP is in whitelist.
        
        Args:
            request: HTTP request object
            
        Returns:
            None if allowed, 403 response if blocked
        """
        from django.conf import settings
        from django.http import HttpResponseForbidden
        
        # Skip if whitelist not configured
        if not hasattr(settings, 'ALLOWED_IPS'):
            return None
        
        # Get client IP
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        # Check whitelist
        allowed_ips = settings.ALLOWED_IPS
        if ip not in allowed_ips:
            logger.warning(f"BLOCKED: Access denied from IP: {ip}")
            return HttpResponseForbidden("Access denied")
        
        return None


class RateLimitMiddleware(MiddlewareMixin):
    """
    Basic rate limiting middleware.
    
    Note: For production, use Django-ratelimit or Redis-based solution.
    This is a simple in-memory implementation for development.
    """
    
    # In-memory storage (use Redis in production)
    _request_counts: dict = {}
    
    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """
        Check rate limit for user/IP.
        
        Args:
            request: HTTP request object
            
        Returns:
            None if within limit, 429 response if exceeded
        """
        from django.http import HttpResponse
        from django.utils import timezone
        from datetime import timedelta
        
        # Get identifier (user or IP)
        if request.user.is_authenticated:
            identifier = f"user_{request.user.id}"
        else:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0].strip()
            else:
                ip = request.META.get('REMOTE_ADDR', 'unknown')
            identifier = f"ip_{ip}"
        
        # Get current minute
        current_minute = timezone.now().replace(second=0, microsecond=0)
        key = f"{identifier}_{current_minute}"
        
        # Check count
        count = self._request_counts.get(key, 0)
        
        # Rate limit: 60 requests per minute
        if count >= 60:
            logger.warning(
                f"RATE_LIMIT: {identifier} exceeded limit "
                f"({count} requests/minute)"
            )
            return HttpResponse(
                "Rate limit exceeded. Please try again later.",
                status=429
            )
        
        # Increment count
        self._request_counts[key] = count + 1
        
        # Cleanup old entries (older than 2 minutes)
        cutoff = current_minute - timedelta(minutes=2)
        keys_to_delete = [
            k for k in self._request_counts.keys()
            if k.split('_')[-1] < str(cutoff)
        ]
        for k in keys_to_delete:
            del self._request_counts[k]
        
        return None
