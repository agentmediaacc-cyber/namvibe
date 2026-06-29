#!/usr/bin/env python3
"""
Phase 10 — Production Reality Audit
Comprehensive audit treating NamVibe as if it has 1 million users tomorrow.
"""

import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple
from collections import defaultdict

BASE_DIR = Path(__file__).parent.parent

class ProductionRealityAudit:
    def __init__(self):
        self.critical = []
        self.high = []
        self.medium = []
        self.low = []
        self.info = []
        self.fixed = []
        
    def add_issue(self, severity: str, category: str, description: str, file_path: str = ""):
        """Add an issue to the appropriate severity list"""
        issue = f"[{category}] {description}"
        if file_path:
            issue += f" ({file_path})"
        
        if severity == "CRITICAL":
            self.critical.append(issue)
        elif severity == "HIGH":
            self.high.append(issue)
        elif severity == "MEDIUM":
            self.medium.append(issue)
        elif severity == "LOW":
            self.low.append(issue)
        else:
            self.info.append(issue)
    
    def search_code_smells(self):
        """Search for TODO, FIXME, placeholder, fake, demo, hardcoded, test user, temporary, mock, sample, legacy, deprecated"""
        print("\n[1] Searching for code smells...")
        
        search_patterns = {
            'TODO': (r'TODO', 'LOW', 'Development comment'),
            'FIXME': (r'FIXME', 'MEDIUM', 'Known issue'),
            'placeholder': (r'placeholder|PLACEHOLDER', 'HIGH', 'Placeholder content'),
            'fake': (r'fake|FAKE', 'CRITICAL', 'Fake data/code'),
            'demo': (r'demo|DEMO', 'MEDIUM', 'Demo code'),
            'hardcoded': (r'hardcoded|HARDCODED', 'HIGH', 'Hardcoded value'),
            'test user': (r'test user|test_user|testuser', 'CRITICAL', 'Test user reference'),
            'temporary': (r'temporary|TEMP', 'MEDIUM', 'Temporary code'),
            'mock': (r'mock|MOCK', 'HIGH', 'Mock data'),
            'sample': (r'sample data|sample_data', 'MEDIUM', 'Sample data'),
            'legacy': (r'legacy|LEGACY', 'MEDIUM', 'Legacy code'),
            'deprecated': (r'deprecated|DEPRECATED', 'HIGH', 'Deprecated code'),
        }
        
        extensions = ['.py', '.html', '.css', '.js', '.sql']
        
        for ext in extensions:
            files = list(BASE_DIR.glob(f"**/*{ext}"))
            for file_path in files:
                if 'node_modules' in str(file_path) or '__pycache__' in str(file_path):
                    continue
                    
                try:
                    content = file_path.read_text(errors='ignore')
                    for pattern_name, (pattern, severity, category) in search_patterns.items():
                        matches = re.findall(pattern, content, re.IGNORECASE)
                        if matches:
                            # Filter out false positives in comments about the patterns themselves
                            for match in matches[:3]:  # Limit to first 3 per file
                                context_start = max(0, content.lower().find(match.lower()) - 50)
                                context_end = min(len(content), content.lower().find(match.lower()) + 50)
                                context = content[context_start:context_end]
                                
                                # Skip if it's in a string literal about the pattern itself
                                if f'search for {pattern_name}' in context.lower():
                                    continue
                                    
                                self.add_issue(severity, category, f"Found '{match}'", str(file_path.relative_to(BASE_DIR)))
                except Exception as e:
                    pass
    
    def check_broken_routes(self):
        """Check for broken navigation and dead buttons"""
        print("\n[2] Checking for broken routes and dead buttons...")
        
        # Check templates for links
        template_files = list((BASE_DIR / "templates").glob("**/*.html"))
        
        for template in template_files:
            try:
                content = template.read_text()
                
                # Check for empty href
                empty_hrefs = re.findall(r'href\s*=\s*["\']\s*["\']', content)
                for href in empty_hrefs:
                    self.add_issue('HIGH', 'Broken Link', f'Empty href attribute', str(template.relative_to(BASE_DIR)))
                
                # Check for href="#"
                hash_links = re.findall(r'href\s*=\s*["\']#["\']', content)
                for link in hash_links:
                    self.add_issue('MEDIUM', 'Broken Link', f'Link to # (no target)', str(template.relative_to(BASE_DIR)))
                
                # Check for buttons without action
                empty_buttons = re.findall(r'<button[^>]*>\s*</button>', content, re.IGNORECASE)
                for btn in empty_buttons:
                    self.add_issue('LOW', 'Dead Button', 'Empty button tag', str(template.relative_to(BASE_DIR)))
                    
            except Exception as e:
                pass
    
    def check_performance_issues(self):
        """Check for performance anti-patterns"""
        print("\n[3] Checking for performance issues...")
        
        # Check Python files for N+1 queries
        python_files = list((BASE_DIR / "services").glob("*.py")) + list((BASE_DIR / "api_routes").glob("*.py"))
        
        for py_file in python_files:
            try:
                content = py_file.read_text()
                
                # Check for potential N+1 queries (loops with DB calls)
                if 'for ' in content and ('query' in content.lower() or 'db' in content.lower()):
                    if re.search(r'for .+ in .+:\s+.*\.(query|execute|fetch)', content, re.DOTALL):
                        self.add_issue('HIGH', 'Performance', 'Potential N+1 query pattern', str(py_file.relative_to(BASE_DIR)))
                
                # Check for SELECT *
                if re.search(r'SELECT\s+\*', content, re.IGNORECASE):
                    self.add_issue('MEDIUM', 'Performance', 'SELECT * usage (should specify columns)', str(py_file.relative_to(BASE_DIR)))
                    
            except Exception as e:
                pass
        
        # Check for duplicate CSS/JS
        css_files = list((BASE_DIR / "static/css").glob("*.css"))
        js_files = list((BASE_DIR / "static/js").glob("*.js"))
        
        if len(css_files) > 20:
            self.add_issue('MEDIUM', 'Performance', f'{len(css_files)} CSS files (consider consolidation)')
        
        if len(js_files) > 20:
            self.add_issue('MEDIUM', 'Performance', f'{len(js_files)} JS files (consider bundling)')
    
    def check_security_issues(self):
        """Check for common security issues"""
        print("\n[4] Checking for security issues...")
        
        python_files = list(BASE_DIR.glob("**/*.py"))
        
        for py_file in python_files:
            if 'test_' in py_file.name or '__pycache__' in str(py_file):
                continue
                
            try:
                content = py_file.read_text()
                
                # Check for SQL injection vulnerabilities
                if re.search(r'execute\s*\([^)]*%s.*\)', content) or re.search(r'execute\s*\([^)]*\+.*\)', content):
                    self.add_issue('CRITICAL', 'Security', 'Potential SQL injection (string formatting in query)', str(py_file.relative_to(BASE_DIR)))
                
                # Check for hardcoded secrets
                if re.search(r'(password|secret|key)\s*=\s*["\'][^"\']+["\']', content, re.IGNORECASE):
                    self.add_issue('CRITICAL', 'Security', 'Potential hardcoded secret', str(py_file.relative_to(BASE_DIR)))
                
                # Check for debug mode in production
                if re.search(r'DEBUG\s*=\s*True', content):
                    self.add_issue('HIGH', 'Security', 'DEBUG mode enabled', str(py_file.relative_to(BASE_DIR)))
                    
            except Exception as e:
                pass
    
    def check_error_handling(self):
        """Check for proper error handling"""
        print("\n[5] Checking error handling...")
        
        python_files = list((BASE_DIR / "api_routes").glob("*.py"))
        
        for py_file in python_files:
            try:
                content = py_file.read_text()
                
                # Check for bare except
                bare_excepts = re.findall(r'except\s*:', content)
                if bare_excepts:
                    self.add_issue('MEDIUM', 'Error Handling', f'{len(bare_excepts)} bare except clauses', str(py_file.relative_to(BASE_DIR)))
                
                # Check for missing try-except around DB operations
                if 'db.' in content and 'try' not in content:
                    self.add_issue('LOW', 'Error Handling', 'Database operations without try-except', str(py_file.relative_to(BASE_DIR)))
                    
            except Exception as e:
                pass
    
    def check_database_issues(self):
        """Check for database-related issues"""
        print("\n[6] Checking database issues...")
        
        # Check for missing indexes
        migration_files = list((BASE_DIR / "migrations").glob("*.sql"))
        if not migration_files:
            self.add_issue('HIGH', 'Database', 'No migration files found')
        
        # Check for large payloads in API routes
        api_files = list((BASE_DIR / "api_routes").glob("*.py"))
        for api_file in api_files:
            try:
                content = api_file.read_text()
                
                # Check for unbounded LIMIT
                if re.search(r'LIMIT\s+\d{4,}', content, re.IGNORECASE):
                    self.add_issue('HIGH', 'Performance', f'Large LIMIT clause (1000+)', str(api_file.relative_to(BASE_DIR)))
                
                # Check for missing pagination
                if 'jsonify' in content and 'page' not in content.lower():
                    self.add_issue('MEDIUM', 'Performance', 'API endpoint may lack pagination', str(api_file.relative_to(BASE_DIR)))
                    
            except Exception as e:
                pass
    
    def check_mobile_responsiveness(self):
        """Check mobile responsiveness"""
        print("\n[7] Checking mobile responsiveness...")
        
        css_files = list((BASE_DIR / "static/css").glob("*.css"))
        
        for css_file in css_files:
            try:
                content = css_file.read_text()
                
                # Check for fixed widths that might break mobile
                fixed_widths = re.findall(r'width:\s*\d+px', content)
                large_fixed = [w for w in fixed_widths if int(re.search(r'\d+', w).group()) > 400]
                
                if large_fixed:
                    self.add_issue('MEDIUM', 'Mobile', f'{len(large_fixed)} fixed widths > 400px', str(css_file.relative_to(BASE_DIR)))
                
                # Check for viewport meta tag
                if css_file.name == 'base.css' or 'base' in css_file.name:
                    if 'viewport' not in content:
                        self.add_issue('HIGH', 'Mobile', 'Missing viewport meta tag')
                        
            except Exception as e:
                pass
    
    def check_consistency(self):
        """Check for consistency across the codebase"""
        print("\n[8] Checking consistency...")
        
        # Check for consistent naming conventions
        css_files = list((BASE_DIR / "static/css").glob("*.css"))
        
        naming_styles = defaultdict(int)
        for css_file in css_files:
            if '_' in css_file.name:
                naming_styles['snake_case'] += 1
            elif '-' in css_file.name:
                naming_styles['kebab-case'] += 1
        
        if len(naming_styles) > 1:
            self.add_issue('LOW', 'Consistency', f'Mixed naming conventions: {dict(naming_styles)}')
    
    def check_unused_code(self):
        """Check for potentially unused code"""
        print("\n[9] Checking for unused code...")
        
        # This is a simplified check - in production you'd use tools like 'vulture' for Python
        template_files = list((BASE_DIR / "templates").glob("**/*.html"))
        
        for template in template_files:
            try:
                content = template.read_text()
                
                # Check for commented out code blocks
                commented_blocks = re.findall(r'<!--\s*{%.*%}.*-->', content, re.DOTALL)
                if commented_blocks:
                    self.add_issue('LOW', 'Cleanup', f'{len(commented_blocks)} commented template blocks', str(template.relative_to(BASE_DIR)))
                    
            except Exception as e:
                pass
    
    def generate_report(self) -> str:
        """Generate comprehensive audit report"""
        report = []
        report.append("=" * 80)
        report.append("NAMVIBE PRODUCTION REALITY AUDIT REPORT")
        report.append("=" * 80)
        report.append("")
        
        # Summary
        total_issues = len(self.critical) + len(self.high) + len(self.medium) + len(self.low)
        report.append("## SUMMARY")
        report.append("")
        report.append(f"Total Issues Found: {total_issues}")
        report.append(f"  - CRITICAL: {len(self.critical)}")
        report.append(f"  - HIGH: {len(self.high)}")
        report.append(f"  - MEDIUM: {len(self.medium)}")
        report.append(f"  - LOW: {len(self.low)}")
        report.append(f"  - INFO: {len(self.info)}")
        report.append(f"  - AUTO-FIXED: {len(self.fixed)}")
        report.append("")
        
        # Critical Issues
        if self.critical:
            report.append("## CRITICAL ISSUES (Must Fix Before Production)")
            report.append("")
            for i, issue in enumerate(self.critical, 1):
                report.append(f"{i}. {issue}")
            report.append("")
        
        # High Priority
        if self.high:
            report.append("## HIGH PRIORITY (Fix Immediately)")
            report.append("")
            for i, issue in enumerate(self.high, 1):
                report.append(f"{i}. {issue}")
            report.append("")
        
        # Medium Priority
        if self.medium:
            report.append("## MEDIUM PRIORITY (Fix Soon)")
            report.append("")
            for i, issue in enumerate(self.medium, 1):
                report.append(f"{i}. {issue}")
            report.append("")
        
        # Low Priority
        if self.low:
            report.append("## LOW PRIORITY (Nice to Have)")
            report.append("")
            for i, issue in enumerate(self.low, 1):
                report.append(f"{i}. {issue}")
            report.append("")
        
        # Info
        if self.info:
            report.append("## INFORMATIONAL")
            report.append("")
            for i, issue in enumerate(self.info, 1):
                report.append(f"{i}. {issue}")
            report.append("")
        
        # Auto-fixed
        if self.fixed:
            report.append("## AUTO-FIXED ISSUES")
            report.append("")
            for i, issue in enumerate(self.fixed, 1):
                report.append(f"{i}. {issue}")
            report.append("")
        
        report.append("=" * 80)
        report.append("")
        
        return "\n".join(report)
    
    def run_audit(self):
        """Run complete production reality audit"""
        print("=" * 80)
        print("NAMVIBE PRODUCTION REALITY AUDIT")
        print("Treating as if 1 million users arrive tomorrow")
        print("=" * 80)
        
        self.search_code_smells()
        self.check_broken_routes()
        self.check_performance_issues()
        self.check_security_issues()
        self.check_error_handling()
        self.check_database_issues()
        self.check_mobile_responsiveness()
        self.check_consistency()
        self.check_unused_code()
        
        report = self.generate_report()
        
        # Save report
        report_path = BASE_DIR / "docs/PRODUCTION_REALITY_AUDIT.md"
        report_path.write_text(report)
        
        print(report)
        
        # Return success if no critical issues
        success = len(self.critical) == 0
        
        if success:
            print("✅ AUDIT PASSED — No critical issues found")
        else:
            print(f"❌ AUDIT FAILED — {len(self.critical)} critical issues must be fixed")
        
        return success

if __name__ == "__main__":
    auditor = ProductionRealityAudit()
    success = auditor.run_audit()
    sys.exit(0 if success else 1)