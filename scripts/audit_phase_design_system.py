#!/usr/bin/env python3
"""
Phase 9 — Design System & UX Audit
Validates unified design system implementation across NamVibe
"""

import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Base paths
BASE_DIR = Path(__file__).parent.parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

class DesignSystemAudit:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.passed = []
        self.design_system_vars = set()
        self.legacy_patterns = []
        
    def audit_css_variables(self) -> bool:
        """Check for duplicate CSS variables across files"""
        print("\n[1] Auditing CSS Variables...")
        
        css_files = list(STATIC_DIR.glob("css/*.css"))
        all_vars = {}
        
        for css_file in css_files:
            content = css_file.read_text()
            # Find CSS custom properties
            vars_found = re.findall(r'--[\w-]+:', content)
            for var in vars_found:
                var_name = var.rstrip(':')
                if var_name not in all_vars:
                    all_vars[var_name] = []
                all_vars[var_name].append(css_file.name)
        
        # Check for duplicates
        duplicates = {k: v for k, v in all_vars.items() if len(v) > 1}
        
        if duplicates:
            self.warnings.append(f"Found {len(duplicates)} potentially duplicate CSS variables")
            for var, files in list(duplicates.items())[:5]:  # Show first 5
                self.warnings.append(f"  {var} defined in: {', '.join(files)}")
        else:
            self.passed.append("No duplicate CSS variables found")
            
        # Check design system is loaded
        base_html = (TEMPLATES_DIR / "base.html").read_text()
        if 'namvibe_design_system.css' in base_html:
            self.passed.append("Design system CSS is loaded in base.html")
        else:
            self.errors.append("Design system CSS NOT loaded in base.html")
            
        return len(self.errors) == 0
    
    def audit_components(self) -> bool:
        """Check for consistent component usage"""
        print("\n[2] Auditing Component Library...")
        
        # Check for legacy component patterns
        legacy_patterns = [
            (r'\.nvpro-', "Legacy nvpro- prefix (should use nv- prefix)"),
            (r'\.chain-', "Legacy chain- prefix (should use nv- prefix)"),
            (r'\.premium-card', "Legacy premium-card (should use nv-card)"),
            (r'\.gen-avatar', "Legacy gen-avatar (should use nv-avatar)"),
        ]
        
        css_files = list(STATIC_DIR.glob("css/*.css"))
        for css_file in css_files:
            if 'design_system' in css_file.name:
                continue  # Skip the design system file itself
                
            content = css_file.read_text()
            for pattern, msg in legacy_patterns:
                matches = re.findall(pattern, content)
                if matches:
                    self.warnings.append(f"{css_file.name}: {msg} ({len(matches)} occurrences)")
        
        # Check for new design system components
        base_html = (TEMPLATES_DIR / "base.html").read_text()
        new_components = ['nv-avatar', 'nv-card', 'nv-btn', 'nv-badge', 'nv-chip']
        
        for component in new_components:
            if component in base_html:
                self.passed.append(f"New component {component} found in base")
            else:
                self.warnings.append(f"New component {component} not yet used in base")
                
        return len(self.errors) == 0
    
    def audit_navigation(self) -> bool:
        """Check navigation consistency"""
        print("\n[3] Auditing Navigation Consistency...")
        
        base_html = (TEMPLATES_DIR / "base.html").read_text()
        
        # Check for consistent nav links
        required_nav = ['/discover/', '/live/', '/reels/', '/status/', '/inbox/']
        for nav in required_nav:
            if nav in base_html:
                self.passed.append(f"Navigation link {nav} present")
            else:
                self.errors.append(f"Missing navigation link: {nav}")
                
        # Check for icon consistency
        if 'fas fa-home' in base_html and 'fas fa-compass' in base_html:
            self.passed.append("Consistent Font Awesome icons used")
        else:
            self.errors.append("Inconsistent or missing navigation icons")
            
        return len(self.errors) == 0
    
    def audit_responsive(self) -> bool:
        """Check responsive breakpoints"""
        print("\n[4] Auditing Responsive Design...")
        
        design_system = (STATIC_DIR / "css/namvibe_design_system.css").read_text()
        
        breakpoints = ['320px', '375px', '390px', '414px', '768px', '1024px', '1440px']
        found_breakpoints = re.findall(r'max-width:\s*(\d+px)|min-width:\s*(\d+px)', design_system)
        
        for bp in breakpoints:
            bp_num = int(bp.replace('px', ''))
            found = any(
                (f'{bp_num}px' in str(found_bp)) 
                for found_bp in found_breakpoints
            )
            if found:
                self.passed.append(f"Breakpoint {bp} covered")
            else:
                self.warnings.append(f"Breakpoint {bp} not explicitly defined")
                
        # Check for mobile-first approach
        if '@media (max-width:' in design_system:
            self.passed.append("Mobile-first media queries found")
        else:
            self.errors.append("No mobile-first media queries found")
            
        return len(self.errors) == 0
    
    def audit_accessibility(self) -> bool:
        """Check accessibility features"""
        print("\n[5] Auditing Accessibility...")
        
        design_system = (STATIC_DIR / "css/namvibe_design_system.css").read_text()
        
        # Check for focus states
        if ':focus-visible' in design_system:
            self.passed.append("Focus states defined")
        else:
            self.errors.append("Missing focus states")
            
        # Check for touch targets
        if 'min-height: 44px' in design_system:
            self.passed.append("Touch targets meet minimum size (44px)")
        else:
            self.errors.append("Touch targets may be too small")
            
        # Check for screen reader only class
        if '.sr-only' in design_system:
            self.passed.append("Screen reader only utility class present")
        else:
            self.warnings.append("Missing sr-only utility class")
            
        return len(self.errors) == 0
    
    def audit_animations(self) -> bool:
        """Check animation consistency"""
        print("\n[6] Auditing Animations...")
        
        design_system = (STATIC_DIR / "css/namvibe_design_system.css").read_text()
        
        required_animations = ['nv-fade-in', 'nv-shimmer', 'nv-spin']
        for anim in required_animations:
            if anim in design_system:
                self.passed.append(f"Animation {anim} defined")
            else:
                self.warnings.append(f"Animation {anim} not found")
                
        # Check for consistent transition timing
        if '--nv-transition-fast' in design_system and '--nv-transition-normal' in design_system:
            self.passed.append("Consistent transition timing variables defined")
        else:
            self.errors.append("Missing transition timing variables")
            
        return len(self.errors) == 0
    
    def audit_legacy_removal(self) -> bool:
        """Check for unused legacy code"""
        print("\n[7] Auditing Legacy Code Removal...")
        
        # Find all CSS files
        css_files = list(STATIC_DIR.glob("css/*.css"))
        
        # Files that should be consolidated
        legacy_indicators = ['_premium.css', '_pro.css', '_engine.css']
        legacy_files = [f for f in css_files if any(indicator in f.name for indicator in legacy_indicators)]
        
        if legacy_files:
            self.warnings.append(f"Found {len(legacy_files)} potentially legacy CSS files:")
            for f in legacy_files[:5]:
                self.warnings.append(f"  - {f.name}")
        else:
            self.passed.append("No obvious legacy CSS files found")
            
        return len(self.errors) == 0
    
    def run_all_audits(self) -> bool:
        """Run all audits and report results"""
        print("=" * 60)
        print("NAMVIBE DESIGN SYSTEM AUDIT")
        print("=" * 60)
        
        results = []
        results.append(self.audit_css_variables())
        results.append(self.audit_components())
        results.append(self.audit_navigation())
        results.append(self.audit_responsive())
        results.append(self.audit_accessibility())
        results.append(self.audit_animations())
        results.append(self.audit_legacy_removal())
        
        # Print summary
        print("\n" + "=" * 60)
        print("AUDIT SUMMARY")
        print("=" * 60)
        
        print(f"\n✅ PASSED ({len(self.passed)}):")
        for item in self.passed:
            print(f"  • {item}")
            
        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for item in self.warnings:
                print(f"  • {item}")
                
        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for item in self.errors:
                print(f"  • {item}")
        
        print("\n" + "=" * 60)
        
        success = len(self.errors) == 0
        if success:
            print("✅ AUDIT PASSED - Design system is properly implemented")
        else:
            print("❌ AUDIT FAILED - Please fix errors before proceeding")
        print("=" * 60 + "\n")
        
        return success

if __name__ == "__main__":
    auditor = DesignSystemAudit()
    success = auditor.run_all_audits()
    sys.exit(0 if success else 1)