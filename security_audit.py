"""
Security Audit Script for ERP System

This script performs a comprehensive security audit of the ERP application,
checking for common vulnerabilities and security misconfigurations.

Usage:
    python security_audit.py

Author: ERP Development Team
Created: 2026-02-04
"""

import os
import sys
import re
from typing import List, Dict, Tuple
from pathlib import Path


class SecurityAuditor:
    """Main security auditor class."""
    
    def __init__(self, project_root: str = "."):
        """
        Initialize security auditor.
        
        Args:
            project_root: Path to project root directory
        """
        self.project_root = Path(project_root)
        self.issues: List[Dict[str, str]] = []
        self.warnings: List[Dict[str, str]] = []
        self.passed: List[str] = []
    
    def add_issue(self, severity: str, category: str, message: str, file: str = "") -> None:
        """Add a security issue."""
        self.issues.append({
            'severity': severity,
            'category': category,
            'message': message,
            'file': file
        })
    
    def add_warning(self, category: str, message: str, file: str = "") -> None:
        """Add a security warning."""
        self.warnings.append({
            'category': category,
            'message': message,
            'file': file
        })
    
    def add_passed(self, check: str) -> None:
        """Add a passed check."""
        self.passed.append(check)
    
    def check_debug_mode(self) -> None:
        """Check if DEBUG is disabled in production."""
        settings_file = self.project_root / 'core_erp' / 'settings.py'
        
        if not settings_file.exists():
            self.add_issue('HIGH', 'Configuration', 
                          'settings.py not found', str(settings_file))
            return
        
        content = settings_file.read_text()
        
        # Check for DEBUG = True
        if re.search(r'DEBUG\s*=\s*True', content, re.IGNORECASE):
            self.add_issue('CRITICAL', 'Configuration',
                          'DEBUG is set to True - MUST be False in production',
                          str(settings_file))
        elif re.search(r'DEBUG\s*=\s*.*getenv.*DEBUG', content):
            self.add_passed('DEBUG configured from environment variable')
        else:
            self.add_passed('DEBUG appears to be disabled')
    
    def check_secret_key(self) -> None:
        """Check SECRET_KEY configuration."""
        settings_file = self.project_root / 'core_erp' / 'settings.py'
        
        if not settings_file.exists():
            return
        
        content = settings_file.read_text()
        
        # Check for hardcoded secret key
        if re.search(r'SECRET_KEY\s*=\s*["\'](?!.*getenv)', content):
            self.add_issue('CRITICAL', 'Security',
                          'SECRET_KEY appears to be hardcoded - use environment variable',
                          str(settings_file))
        else:
            self.add_passed('SECRET_KEY configured from environment')
    
    def check_allowed_hosts(self) -> None:
        """Check ALLOWED_HOSTS configuration."""
        settings_file = self.project_root / 'core_erp' / 'settings.py'
        
        if not settings_file.exists():
            return
        
        content = settings_file.read_text()
        
        # Check for wildcard in ALLOWED_HOSTS
        if re.search(r'ALLOWED_HOSTS\s*=\s*\[\s*["\'][*]["\']', content):
            self.add_issue('HIGH', 'Configuration',
                          'ALLOWED_HOSTS contains wildcard (*) - specify exact domains',
                          str(settings_file))
        elif re.search(r'ALLOWED_HOSTS\s*=\s*\[\s*\]', content):
            self.add_issue('HIGH', 'Configuration',
                          'ALLOWED_HOSTS is empty - add your domain(s)',
                          str(settings_file))
        else:
            self.add_passed('ALLOWED_HOSTS appears properly configured')
    
    def check_https_settings(self) -> None:
        """Check HTTPS/SSL security settings."""
        settings_file = self.project_root / 'core_erp' / 'settings.py'
        
        if not settings_file.exists():
            return
        
        content = settings_file.read_text()
        
        checks = {
            'SECURE_SSL_REDIRECT': 'SSL redirect not enabled',
            'SESSION_COOKIE_SECURE': 'Session cookies not secure',
            'CSRF_COOKIE_SECURE': 'CSRF cookies not secure',
            'SECURE_HSTS_SECONDS': 'HSTS not configured',
        }
        
        for setting, message in checks.items():
            if setting not in content:
                self.add_warning('HTTPS', message, str(settings_file))
            else:
                self.add_passed(f'{setting} configured')
    
    def check_sql_injection(self) -> None:
        """Check for potential SQL injection vulnerabilities."""
        python_files = list(self.project_root.rglob('*.py'))
        
        dangerous_patterns = [
            (r'\.raw\(["\'].*%s.*["\']', 'Potential SQL injection in raw() query'),
            (r'\.extra\(.*where=.*%', 'Potential SQL injection in extra() clause'),
            (r'cursor\.execute\(["\'].*%.*["\']', 'Potential SQL injection in cursor.execute()'),
        ]
        
        for py_file in python_files:
            if 'migrations' in str(py_file) or 'venv' in str(py_file):
                continue
            
            try:
                content = py_file.read_text()
                
                for pattern, message in dangerous_patterns:
                    if re.search(pattern, content):
                        self.add_issue('HIGH', 'SQL Injection',
                                      message, str(py_file))
            except Exception:
                pass
    
    def check_xss_vulnerabilities(self) -> None:
        """Check for potential XSS vulnerabilities in templates."""
        template_files = list(self.project_root.rglob('*.html'))
        
        for template in template_files:
            try:
                content = template.read_text()
                
                # Check for |safe filter usage
                if '|safe' in content:
                    self.add_warning('XSS',
                                    'Template uses |safe filter - ensure data is sanitized',
                                    str(template))
                
                # Check for mark_safe usage
                if 'mark_safe' in content:
                    self.add_warning('XSS',
                                    'Template uses mark_safe - ensure data is sanitized',
                                    str(template))
            except Exception:
                pass
    
    def check_sensitive_data_exposure(self) -> None:
        """Check for exposed sensitive data in code."""
        python_files = list(self.project_root.rglob('*.py'))
        
        sensitive_patterns = [
            (r'password\s*=\s*["\'][^"\']+["\']', 'Hardcoded password detected'),
            (r'api_key\s*=\s*["\'][^"\']+["\']', 'Hardcoded API key detected'),
            (r'secret\s*=\s*["\'][^"\']+["\']', 'Hardcoded secret detected'),
            (r'token\s*=\s*["\'][^"\']+["\']', 'Hardcoded token detected'),
        ]
        
        for py_file in python_files:
            if 'migrations' in str(py_file) or 'venv' in str(py_file):
                continue
            
            try:
                content = py_file.read_text()
                
                for pattern, message in sensitive_patterns:
                    matches = re.finditer(pattern, content, re.IGNORECASE)
                    for match in matches:
                        # Skip if it's a getenv call
                        if 'getenv' in match.group(0):
                            continue
                        
                        self.add_issue('CRITICAL', 'Sensitive Data',
                                      message, str(py_file))
            except Exception:
                pass
    
    def check_csrf_protection(self) -> None:
        """Check CSRF protection in templates."""
        template_files = list(self.project_root.rglob('*.html'))
        
        for template in template_files:
            try:
                content = template.read_text()
                
                # Check for forms without csrf_token
                if '<form' in content and 'method="post"' in content.lower():
                    if 'csrf_token' not in content.lower():
                        self.add_warning('CSRF',
                                        'POST form without CSRF token',
                                        str(template))
            except Exception:
                pass
    
    def check_file_permissions(self) -> None:
        """Check file permissions for sensitive files."""
        sensitive_files = [
            '.env',
            'core_erp/settings.py',
            'db.sqlite3',
        ]
        
        for file_path in sensitive_files:
            full_path = self.project_root / file_path
            
            if not full_path.exists():
                continue
            
            # Check if file is readable by others (Linux/Mac only)
            try:
                import stat
                file_stat = full_path.stat()
                mode = file_stat.st_mode
                
                if mode & stat.S_IROTH:
                    self.add_warning('File Permissions',
                                    f'{file_path} is readable by others',
                                    str(full_path))
            except Exception:
                pass
    
    def check_dependencies(self) -> None:
        """Check for outdated/vulnerable dependencies."""
        requirements_file = self.project_root / 'requirements.txt'
        
        if not requirements_file.exists():
            self.add_warning('Dependencies',
                            'requirements.txt not found')
            return
        
        content = requirements_file.read_text()
        
        # Check for unpinned versions
        if re.search(r'^[a-zA-Z0-9-]+$', content, re.MULTILINE):
            self.add_warning('Dependencies',
                            'Some dependencies not pinned to specific versions',
                            str(requirements_file))
        else:
            self.add_passed('All dependencies appear to be pinned')
    
    def run_all_checks(self) -> None:
        """Run all security checks."""
        print("🔒 Running Security Audit...\n")
        
        checks = [
            ("Checking DEBUG mode", self.check_debug_mode),
            ("Checking SECRET_KEY", self.check_secret_key),
            ("Checking ALLOWED_HOSTS", self.check_allowed_hosts),
            ("Checking HTTPS settings", self.check_https_settings),
            ("Checking SQL injection", self.check_sql_injection),
            ("Checking XSS vulnerabilities", self.check_xss_vulnerabilities),
            ("Checking sensitive data exposure", self.check_sensitive_data_exposure),
            ("Checking CSRF protection", self.check_csrf_protection),
            ("Checking file permissions", self.check_file_permissions),
            ("Checking dependencies", self.check_dependencies),
        ]
        
        for description, check_func in checks:
            print(f"⏳ {description}...")
            try:
                check_func()
            except Exception as e:
                print(f"  ❌ Error: {e}")
        
        print()
    
    def print_report(self) -> None:
        """Print security audit report."""
        print("=" * 70)
        print("SECURITY AUDIT REPORT")
        print("=" * 70)
        print()
        
        # Critical issues
        critical_issues = [i for i in self.issues if i['severity'] == 'CRITICAL']
        if critical_issues:
            print(f"🔴 CRITICAL ISSUES ({len(critical_issues)}):")
            print("-" * 70)
            for issue in critical_issues:
                print(f"  [{issue['category']}] {issue['message']}")
                if issue['file']:
                    print(f"    File: {issue['file']}")
                print()
        
        # High severity issues
        high_issues = [i for i in self.issues if i['severity'] == 'HIGH']
        if high_issues:
            print(f"🟠 HIGH SEVERITY ISSUES ({len(high_issues)}):")
            print("-" * 70)
            for issue in high_issues:
                print(f"  [{issue['category']}] {issue['message']}")
                if issue['file']:
                    print(f"    File: {issue['file']}")
                print()
        
        # Warnings
        if self.warnings:
            print(f"🟡 WARNINGS ({len(self.warnings)}):")
            print("-" * 70)
            for warning in self.warnings:
                print(f"  [{warning['category']}] {warning['message']}")
                if warning['file']:
                    print(f"    File: {warning['file']}")
                print()
        
        # Passed checks
        if self.passed:
            print(f"✅ PASSED CHECKS ({len(self.passed)}):")
            print("-" * 70)
            for check in self.passed:
                print(f"  ✓ {check}")
            print()
        
        # Summary
        print("=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"Critical Issues: {len(critical_issues)}")
        print(f"High Severity:   {len(high_issues)}")
        print(f"Warnings:        {len(self.warnings)}")
        print(f"Passed:          {len(self.passed)}")
        print()
        
        # Security score
        total_checks = len(self.issues) + len(self.warnings) + len(self.passed)
        if total_checks > 0:
            score = (len(self.passed) / total_checks) * 100
            print(f"Security Score:  {score:.1f}%")
            
            if score >= 90:
                grade = "A+"
            elif score >= 80:
                grade = "A"
            elif score >= 70:
                grade = "B"
            elif score >= 60:
                grade = "C"
            else:
                grade = "F"
            
            print(f"Grade:           {grade}")
        
        print("=" * 70)
        
        # Exit code
        if critical_issues or high_issues:
            print("\n❌ Security audit FAILED")
            sys.exit(1)
        elif self.warnings:
            print("\n⚠️  Security audit PASSED with warnings")
            sys.exit(0)
        else:
            print("\n✅ Security audit PASSED")
            sys.exit(0)


def main():
    """Main entry point."""
    auditor = SecurityAuditor(".")
    auditor.run_all_checks()
    auditor.print_report()


if __name__ == '__main__':
    main()
