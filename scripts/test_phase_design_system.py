#!/usr/bin/env python3
"""
Phase 9 — Design System Tests
Tests for unified design system implementation
"""

import os
import sys
import unittest
from pathlib import Path
from audit_phase_design_system import DesignSystemAudit

BASE_DIR = Path(__file__).parent.parent

class TestDesignSystem(unittest.TestCase):
    def setUp(self):
        self.auditor = DesignSystemAudit()
    
    def test_design_system_loaded(self):
        """Test that design system CSS is loaded"""
        base_html = (BASE_DIR / "templates/base.html").read_text()
        self.assertIn('namvibe_design_system.css', base_html)
    
    def test_design_system_has_tokens(self):
        """Test that design system has required tokens"""
        css = (BASE_DIR / "static/css/namvibe_design_system.css").read_text()
        required_tokens = [
            '--nv-color-bg-primary',
            '--nv-color-accent',
            '--nv-font-family',
            '--nv-space-4',
            '--nv-radius-lg',
            '--nv-shadow-md',
            '--nv-transition-fast',
        ]
        for token in required_tokens:
            self.assertIn(token, css, f"Missing design token: {token}")
    
    def test_design_system_has_components(self):
        """Test that design system has required components"""
        css = (BASE_DIR / "static/css/namvibe_design_system.css").read_text()
        required_components = [
            '.nv-avatar',
            '.nv-card',
            '.nv-btn',
            '.nv-badge',
            '.nv-chip',
            '.nv-input',
            '.nv-modal',
            '.nv-toast',
            '.nv-skeleton',
            '.nv-empty-state',
        ]
        for component in required_components:
            self.assertIn(component, css, f"Missing component: {component}")
    
    def test_design_system_has_responsive(self):
        """Test that design system has responsive breakpoints"""
        css = (BASE_DIR / "static/css/namvibe_design_system.css").read_text()
        self.assertIn('@media (max-width:', css)
        self.assertIn('@media (min-width:', css)
    
    def test_design_system_has_accessibility(self):
        """Test that design system has accessibility features"""
        css = (BASE_DIR / "static/css/namvibe_design_system.css").read_text()
        self.assertIn(':focus-visible', css)
        self.assertIn('min-height: 44px', css)
        self.assertIn('.sr-only', css)
    
    def test_design_system_has_animations(self):
        """Test that design system has consistent animations"""
        css = (BASE_DIR / "static/css/namvibe_design_system.css").read_text()
        required_animations = ['nv-fade-in', 'nv-shimmer', 'nv-spin']
        for anim in required_animations:
            self.assertIn(anim, css, f"Missing animation: {anim}")
    
    def test_navigation_consistency(self):
        """Test that navigation is consistent"""
        result = self.auditor.audit_navigation()
        self.assertTrue(result)
        self.assertEqual(len(self.auditor.errors), 0)
    
    def test_no_critical_errors(self):
        """Test that audit passes with no critical errors"""
        result = self.auditor.run_all_audits()
        self.assertTrue(result)
        self.assertEqual(len(self.auditor.errors), 0)

if __name__ == '__main__':
    unittest.main()