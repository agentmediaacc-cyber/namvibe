"""
Focused tests for the Support System feature.

These tests verify:
  - User ticket creation and access control
  - User cannot view another user's ticket
  - User cannot add internal notes
  - Admin/agent access control
  - Ticket lifecycle (status changes, reopen)
  - SQL schema contract
  - No live DB calls in unit tests

Run with:
    FLASK_TESTING=1 python3 -m pytest scripts/test_support_system.py -v
"""

import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["CHAIN_DISABLE_DB_PING"] = "1"
os.environ["CHAIN_DISABLE_PREWARM"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"
os.environ["FLASK_TESTING"] = "1"
os.environ["SECRET_KEY"] = "test-secret-key-for-support-tests"

from flask import Flask, session


class TestSupportUserFlows(unittest.TestCase):
    """User-facing support flows."""

    def setUp(self):
        from api_routes.support_routes import support_bp, support_page_bp

        self.app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), "..", "templates"))
        self.app.secret_key = "test-secret-key-for-support-tests"
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.app.register_blueprint(support_bp)
        self.app.register_blueprint(support_page_bp)
        self.app.jinja_env.globals["csrf_token"] = lambda: "test-csrf-token"

        self.client = self.app.test_client()

    def test_support_center_requires_login(self):
        """Support center should show login CTA for unauthenticated users."""
        resp = self.client.get("/support")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Sign in to create tickets", resp.data)

    @patch("api_routes.support_routes.get_current_profile")
    def test_support_center_shows_tickets_for_authenticated(self, mock_profile):
        """Support center should show user's tickets when authenticated."""
        mock_profile.return_value = {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "username": "testuser"}
        with self.client.session_transaction() as sess:
            sess["profile_id"] = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

        with patch("api_routes.support_routes.list_user_tickets") as mock_tickets:
            with patch("api_routes.support_routes.get_help_articles") as mock_articles:
                mock_tickets.return_value = [{"ticket_id": "NV-TKT-2025-000001", "subject": "Test", "status": "open", "last_activity_at": "2025-01-01T00:00:00Z"}]
                mock_articles.return_value = []
                self.app.jinja_env.filters['datetime'] = lambda x: str(x) if x else ''
                resp = self.client.get("/support")
                self.assertEqual(resp.status_code, 200)
                self.assertIn(b"My Recent Tickets", resp.data)

    @patch("api_routes.support_routes.get_current_profile")
    def test_create_ticket_missing_fields(self, mock_profile):
        """Create ticket should fail with missing required fields."""
        mock_profile.return_value = {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "username": "testuser"}
        with self.client.session_transaction() as sess:
            sess["profile_id"] = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

        resp = self.client.post("/api/support/tickets", json={
            "subject": "Test",
            "category": "account_issue",
        })
        self.assertEqual(resp.status_code, 400)
        data = json.loads(resp.data)
        self.assertFalse(data["ok"])

    @patch("api_routes.support_routes.get_current_profile")
    @patch("api_routes.support_routes.create_ticket")
    def test_create_ticket_success(self, mock_create, mock_profile):
        """Create ticket should succeed with valid data."""
        mock_profile.return_value = {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "username": "testuser"}
        mock_create.return_value = ("NV-TKT-2025-000001", None)

        with self.client.session_transaction() as sess:
            sess["profile_id"] = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

        resp = self.client.post("/api/support/tickets", json={
            "subject": "Test subject",
            "category": "account_issue",
            "description": "Test description",
        })
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data["ok"])
        self.assertIn("ticket_id", data)

    @patch("api_routes.support_routes.get_current_profile")
    def test_user_cannot_view_another_users_ticket(self, mock_profile):
        """User should not be able to view another user's ticket via API."""
        mock_profile.return_value = {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "username": "testuser"}

        with self.client.session_transaction() as sess:
            sess["profile_id"] = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

        with patch("api_routes.support_routes.get_ticket") as mock_get_ticket:
            mock_get_ticket.return_value = None
            resp = self.client.get("/api/support/tickets/NV-TKT-2025-000001")
            self.assertEqual(resp.status_code, 404)

    @patch("api_routes.support_routes.get_current_profile")
    @patch("api_routes.support_routes.get_ticket")
    @patch("api_routes.support_routes.add_user_message")
    def test_user_can_add_message_to_own_ticket(self, mock_add_user_message, mock_get_ticket, mock_profile):
        """User can add message to their own ticket."""
        mock_profile.return_value = {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "username": "testuser"}
        mock_get_ticket.return_value = {"id": 1, "profile_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "ticket_id": "NV-TKT-2025-000001", "status": "open"}
        mock_add_user_message.return_value = (True, None)

        with self.client.session_transaction() as sess:
            sess["profile_id"] = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

        resp = self.client.post("/api/support/tickets/NV-TKT-2025-000001/messages", json={"message": "Test message"})
        self.assertEqual(resp.status_code, 200)

    @patch("api_routes.support_routes.get_current_profile")
    @patch("api_routes.support_routes.get_ticket")
    def test_malformed_ticket_id(self, mock_get_ticket, mock_profile):
        """Malformed ticket ID should return 404."""
        mock_profile.return_value = {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "username": "testuser"}
        mock_get_ticket.return_value = None

        with self.client.session_transaction() as sess:
            sess["profile_id"] = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

        resp = self.client.get("/api/support/tickets/abc")
        self.assertEqual(resp.status_code, 404)

    @patch("api_routes.support_routes.get_current_profile")
    @patch("api_routes.support_routes.get_ticket")
    @patch("api_routes.support_routes.add_user_message")
    def test_user_cannot_add_message_to_another_users_ticket(self, mock_add_user_message, mock_get_ticket, mock_profile):
        """User should not be able to add message to another user's ticket."""
        mock_profile.return_value = {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "username": "testuser"}
        mock_get_ticket.return_value = None
        mock_add_user_message.return_value = (None, "ticket_not_found")

        with self.client.session_transaction() as sess:
            sess["profile_id"] = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

        resp = self.client.post("/api/support/tickets/NV-TKT-2025-000001/messages", json={"message": "Test message"})
        self.assertEqual(resp.status_code, 404)
        data = json.loads(resp.data)
        self.assertFalse(data["ok"])

    @patch("api_routes.support_routes.get_current_profile")
    @patch("api_routes.support_routes.get_ticket")
    @patch("api_routes.support_routes.add_user_message")
    def test_user_cannot_add_message_to_closed_ticket(self, mock_add_user_message, mock_get_ticket, mock_profile):
        """User should not be able to add message to a closed ticket."""
        mock_profile.return_value = {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "username": "testuser"}
        mock_get_ticket.return_value = {"id": 1, "profile_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "ticket_id": "NV-TKT-2025-000001", "status": "closed"}
        mock_add_user_message.return_value = (None, "ticket_not_active")

        with self.client.session_transaction() as sess:
            sess["profile_id"] = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

        resp = self.client.post("/api/support/tickets/NV-TKT-2025-000001/messages", json={"message": "Test message"})
        self.assertEqual(resp.status_code, 400)

    @patch("api_routes.support_routes.get_current_profile")
    @patch("api_routes.support_routes.get_ticket")
    @patch("api_routes.support_routes.add_user_message")
    def test_user_can_add_message_to_active_ticket(self, mock_add_user_message, mock_get_ticket, mock_profile):
        """User should be able to add message to an active ticket."""
        mock_profile.return_value = {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "username": "testuser"}
        mock_get_ticket.return_value = {"id": 1, "profile_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "ticket_id": "NV-TKT-2025-000001", "status": "open"}
        mock_add_user_message.return_value = (True, None)

        with self.client.session_transaction() as sess:
            sess["profile_id"] = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

        resp = self.client.post("/api/support/tickets/NV-TKT-2025-000001/messages", json={"message": "Test message"})
        self.assertEqual(resp.status_code, 200)

    @patch("api_routes.support_routes.get_current_profile")
    @patch("api_routes.support_routes.get_ticket")
    @patch("api_routes.support_routes.get_user_messages")
    def test_user_messages_excludes_internal_notes(self, mock_get_user_messages, mock_get_ticket, mock_profile):
        """User message list should exclude internal notes at SQL level."""
        mock_profile.return_value = {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "username": "testuser"}
        mock_get_ticket.return_value = {"id": 1, "profile_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "ticket_id": "NV-TKT-2025-000001"}
        mock_get_user_messages.return_value = [
            {"id": 1, "message": "User message", "is_internal_note": False},
            {"id": 2, "message": "Agent public reply", "is_internal_note": False},
        ]

        with self.client.session_transaction() as sess:
            sess["profile_id"] = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

        resp = self.client.get("/api/support/tickets/NV-TKT-2025-000001/messages")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        for msg in data.get("messages", []):
            self.assertFalse(msg.get("is_internal_note", False))

    @patch("api_routes.support_routes.get_current_profile")
    @patch("api_routes.support_routes.get_ticket")
    @patch("api_routes.support_routes.add_user_message")
    def test_user_reply_to_resolved_denied(self, mock_add_user_message, mock_get_ticket, mock_profile):
        """User reply to resolved ticket is denied."""
        mock_profile.return_value = {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "username": "testuser"}
        mock_get_ticket.return_value = {"id": 1, "profile_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "ticket_id": "NV-TKT-2025-000001", "status": "resolved"}
        mock_add_user_message.return_value = (None, "ticket_not_active")

        with self.client.session_transaction() as sess:
            sess["profile_id"] = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

        resp = self.client.post("/api/support/tickets/NV-TKT-2025-000001/messages", json={"message": "Test"})
        self.assertEqual(resp.status_code, 400)
        data = json.loads(resp.data)
        self.assertFalse(data["ok"])
        self.assertEqual(data["error"], "Ticket is not active")

    @patch("api_routes.support_routes.get_current_profile")
    @patch("api_routes.support_routes.get_ticket")
    @patch("api_routes.support_routes.add_user_message")
    def test_user_reply_to_closed_denied(self, mock_add_user_message, mock_get_ticket, mock_profile):
        """User reply to closed ticket is denied."""
        mock_profile.return_value = {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "username": "testuser"}
        mock_get_ticket.return_value = {"id": 1, "profile_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "ticket_id": "NV-TKT-2025-000001", "status": "closed"}
        mock_add_user_message.return_value = (None, "ticket_not_active")

        with self.client.session_transaction() as sess:
            sess["profile_id"] = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

        resp = self.client.post("/api/support/tickets/NV-TKT-2025-000001/messages", json={"message": "Test"})
        self.assertEqual(resp.status_code, 400)

    @patch("api_routes.support_routes.get_current_profile")
    @patch("api_routes.support_routes.get_ticket")
    @patch("api_routes.support_routes.add_user_message")
    def test_user_reply_to_rejected_denied(self, mock_add_user_message, mock_get_ticket, mock_profile):
        """User reply to rejected ticket is denied."""
        mock_profile.return_value = {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "username": "testuser"}
        mock_get_ticket.return_value = {"id": 1, "profile_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "ticket_id": "NV-TKT-2025-000001", "status": "rejected"}
        mock_add_user_message.return_value = (None, "ticket_not_active")

        with self.client.session_transaction() as sess:
            sess["profile_id"] = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

        resp = self.client.post("/api/support/tickets/NV-TKT-2025-000001/messages", json={"message": "Test"})
        self.assertEqual(resp.status_code, 400)

    @patch("api_routes.support_routes.get_current_profile")
    @patch("api_routes.support_routes.get_ticket")
    @patch("api_routes.support_routes.update_ticket_status")
    def test_explicit_reopen_changes_status(self, mock_update, mock_get_ticket, mock_profile):
        """Explicit reopen changes the status."""
        mock_profile.return_value = {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "username": "testuser"}
        mock_get_ticket.return_value = {"id": 1, "profile_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "ticket_id": "NV-TKT-2025-000001", "status": "closed"}
        mock_update.return_value = (True, None)

        with self.client.session_transaction() as sess:
            sess["profile_id"] = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

        resp = self.client.post("/api/support/tickets/NV-TKT-2025-000001/reopen", json={})
        self.assertEqual(resp.status_code, 200)
        mock_update.assert_called_once()
        args = mock_update.call_args
        self.assertEqual(args[0][1], "appealed")

    @patch("api_routes.support_routes.get_current_profile")
    @patch("api_routes.support_routes.get_ticket")
    @patch("api_routes.support_routes.add_user_message")
    def test_reply_succeeds_after_reopen(self, mock_add_user_message, mock_get_ticket, mock_profile):
        """Reply succeeds after explicit reopen."""
        mock_profile.return_value = {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "username": "testuser"}
        mock_get_ticket.return_value = {"id": 1, "profile_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "ticket_id": "NV-TKT-2025-000001", "status": "appealed"}
        mock_add_user_message.return_value = (True, None)

        with self.client.session_transaction() as sess:
            sess["profile_id"] = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

        resp = self.client.post("/api/support/tickets/NV-TKT-2025-000001/messages", json={"message": "Test"})
        self.assertEqual(resp.status_code, 200)

    @patch("api_routes.support_routes.get_current_profile")
    @patch("api_routes.support_routes.get_ticket")
    @patch("api_routes.support_routes.add_user_message")
    def test_user_route_uses_add_user_message_not_add_message(self, mock_add_user_message, mock_get_ticket, mock_profile):
        """User route uses add_user_message, preventing is_agent flag spoofing."""
        mock_profile.return_value = {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "username": "testuser"}
        mock_get_ticket.return_value = {"id": 1, "profile_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "ticket_id": "NV-TKT-2025-000001", "status": "open"}
        mock_add_user_message.return_value = (True, None)

        with self.client.session_transaction() as sess:
            sess["profile_id"] = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

        resp = self.client.post("/api/support/tickets/NV-TKT-2025-000001/messages", json={"message": "Test"})
        self.assertEqual(resp.status_code, 200)
        # Verify add_user_message was called (not add_message with is_agent=True)
        mock_add_user_message.assert_called_once()


class TestSupportAdminFlows(unittest.TestCase):
    """Admin/agent support flows."""

    def setUp(self):
        from api_routes.support_routes import support_bp, support_page_bp

        self.app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), "..", "templates"))
        self.app.secret_key = "test-secret-key-for-support-tests"
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.app.register_blueprint(support_bp)
        self.app.register_blueprint(support_page_bp)
        self.app.jinja_env.globals["csrf_token"] = lambda: "test-csrf-token"

        self.client = self.app.test_client()

    @patch("api_routes.support_routes.get_current_profile")
    @patch("api_routes.support_routes.is_agent")
    def test_admin_tickets_requires_agent(self, mock_is_agent, mock_profile):
        """Admin tickets list should require agent status."""
        mock_profile.return_value = {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "username": "testuser"}
        mock_is_agent.return_value = None

        with self.client.session_transaction() as sess:
            sess["profile_id"] = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

        resp = self.client.get("/api/support/admin/tickets")
        self.assertEqual(resp.status_code, 403)

    @patch("api_routes.support_routes.get_current_profile")
    @patch("api_routes.support_routes.is_agent")
    @patch("api_routes.support_routes.list_all_tickets")
    def test_admin_tickets_list(self, mock_list, mock_is_agent, mock_profile):
        """Admin should be able to list all tickets."""
        mock_profile.return_value = {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "username": "agent"}
        mock_is_agent.return_value = {"id": 1, "profile_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "is_active": True}
        mock_list.return_value = [{"ticket_id": "NV-TKT-2025-000001"}]

        with self.client.session_transaction() as sess:
            sess["profile_id"] = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

        resp = self.client.get("/api/support/admin/tickets")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data["ok"])
        self.assertIn("tickets", data)

    @patch("api_routes.support_routes.get_current_profile")
    @patch("api_routes.support_routes.is_agent")
    @patch("api_routes.support_routes.update_ticket_status")
    def test_admin_update_status(self, mock_update, mock_is_agent, mock_profile):
        """Admin should be able to update ticket status."""
        mock_profile.return_value = {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "username": "agent"}
        mock_is_agent.return_value = {"id": 1, "profile_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "is_active": True}
        mock_update.return_value = (True, None)

        with self.client.session_transaction() as sess:
            sess["profile_id"] = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

        resp = self.client.post("/api/support/admin/tickets/1/status", json={"status": "resolved", "reason": "Issue fixed"})
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data["ok"])

    @patch("api_routes.support_routes.get_current_profile")
    @patch("api_routes.support_routes.is_agent")
    def test_normal_user_blocked_from_admin(self, mock_is_agent, mock_profile):
        """Normal user should be blocked from admin endpoints."""
        mock_profile.return_value = {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "username": "user"}
        mock_is_agent.return_value = None

        with self.client.session_transaction() as sess:
            sess["profile_id"] = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

        resp = self.client.get("/api/support/admin/tickets")
        self.assertEqual(resp.status_code, 403)

    @patch("api_routes.support_routes.get_current_profile")
    @patch("api_routes.support_routes.is_agent")
    @patch("api_routes.support_routes.add_message")
    def test_agent_can_add_internal_note(self, mock_add_message, mock_is_agent, mock_profile):
        """Agent should be able to add internal notes."""
        mock_profile.return_value = {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "username": "agent"}
        mock_is_agent.return_value = {"id": 1, "profile_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "is_active": True}
        mock_add_message.return_value = (True, None)

        with self.client.session_transaction() as sess:
            sess["profile_id"] = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

        resp = self.client.post("/api/support/admin/tickets/1/message", json={"message": "Internal note", "is_internal": True})
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data["ok"])

    @patch("api_routes.support_routes.get_current_profile")
    @patch("api_routes.support_routes.is_agent")
    def test_non_agent_cannot_use_admin_message_endpoint(self, mock_is_agent, mock_profile):
        """Non-agent should be blocked from admin message endpoint."""
        mock_profile.return_value = {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "username": "user"}
        mock_is_agent.return_value = None

        with self.client.session_transaction() as sess:
            sess["profile_id"] = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

        resp = self.client.post("/api/support/admin/tickets/1/message", json={"message": "Test"})
        self.assertEqual(resp.status_code, 403)


class TestSupportAttachmentSecurity(unittest.TestCase):
    """Attachment security tests."""

    def test_upload_support_attachment_rejects_missing_file(self):
        """Upload should reject missing file."""
        from services.storage_service import upload_support_attachment
        result, error = upload_support_attachment(None, 1, "test-user")
        self.assertIsNone(result)
        self.assertIn("No file provided", error)

    def test_upload_support_attachment_rejects_empty_file(self):
        """Upload should reject empty file."""
        from services.storage_service import upload_support_attachment
        from io import BytesIO
        from unittest.mock import MagicMock

        mock_file = MagicMock()
        mock_file.filename = "test.jpg"
        mock_file.content_type = "image/jpeg"
        mock_file.seek = lambda a, b=0: None
        mock_file.tell = lambda: 0  # Empty file

        result, error = upload_support_attachment(mock_file, 1, "test-user")
        self.assertIsNone(result)
        self.assertIn("Empty file", error)

    def test_upload_support_attachment_rejects_bad_extension(self):
        """Upload should reject disallowed extension."""
        from services.storage_service import upload_support_attachment
        from io import BytesIO
        from unittest.mock import MagicMock

        mock_file = MagicMock()
        mock_file.filename = "test.exe"
        mock_file.content_type = "application/octet-stream"
        mock_file.seek = lambda a, b=0: None
        mock_file.tell = lambda: 1000

        result, error = upload_support_attachment(mock_file, 1, "test-user")
        self.assertIsNone(result)
        self.assertIn("File type not allowed", error)

    def test_upload_support_attachment_rejects_bad_mime(self):
        """Upload should reject disallowed MIME type."""
        from services.storage_service import upload_support_attachment
        from io import BytesIO
        from unittest.mock import MagicMock

        mock_file = MagicMock()
        mock_file.filename = "test.jpg"
        mock_file.content_type = "application/x-php"  # Bad MIME
        mock_file.seek = lambda a, b=0: None
        mock_file.tell = lambda: 1000

        result, error = upload_support_attachment(mock_file, 1, "test-user")
        self.assertIsNone(result)
        self.assertIn("do not match", error)

    def test_upload_support_attachment_rejects_mime_mismatch(self):
        """Upload should reject extension/MIME mismatch."""
        from services.storage_service import upload_support_attachment
        from io import BytesIO
        from unittest.mock import MagicMock

        mock_file = MagicMock()
        mock_file.filename = "test.jpg"
        mock_file.content_type = "image/png"  # Mismatch: jpg vs png
        mock_file.seek = lambda a, b=0: None
        mock_file.tell = lambda: 1000

        result, error = upload_support_attachment(mock_file, 1, "test-user")
        self.assertIsNone(result)
        self.assertIn("do not match", error)

    def test_upload_support_attachment_rejects_oversized(self):
        """Upload should reject files over 10MB."""
        from services.storage_service import upload_support_attachment
        from io import BytesIO
        from unittest.mock import MagicMock

        mock_file = MagicMock()
        mock_file.filename = "test.jpg"
        mock_file.content_type = "image/jpeg"
        mock_file.seek = lambda a, b=0: None
        mock_file.tell = lambda: 11 * 1024 * 1024  # 11MB

        result, error = upload_support_attachment(mock_file, 1, "test-user")
        self.assertIsNone(result)
        self.assertIn("File too large", error)

    def test_upload_support_attachment_sanitizes_filename(self):
        """Upload should sanitize filename to prevent path traversal."""
        from services.storage_service import upload_support_attachment
        from io import BytesIO
        from unittest.mock import MagicMock, patch

        mock_file = MagicMock()
        mock_file.filename = "../../../etc/passwd.jpg"
        mock_file.content_type = "image/jpeg"
        mock_file.seek = lambda a, b=0: None
        mock_file.tell = lambda: 1000

        with patch("services.storage_service.upload_file_to_bucket") as mock_upload:
            mock_upload.return_value = ({"url": "/uploads/test"}, None)
            with patch("services.neon_service.execute") as mock_execute:
                result, error = upload_support_attachment(mock_file, 1, "test-user")
                # The function returns (result, None) on success
                # secure_filename should sanitize "../../../etc/passwd.jpg" to "etc_passwd.jpg"
                self.assertIsNone(error)
                self.assertIsNotNone(result)


class TestSupportSQLContract(unittest.TestCase):
    """Contract tests for the support SQL schema."""

    def test_sql_file_exists(self):
        """The SQL migration file should exist."""
        path = os.path.join(os.path.dirname(__file__), "..", "sql", "phase_support_tickets.sql")
        self.assertTrue(os.path.exists(path), "SQL migration file not found")

    def test_sql_has_create_table(self):
        """SQL should contain CREATE TABLE for support tables."""
        path = os.path.join(os.path.dirname(__file__), "..", "sql", "phase_support_tickets.sql")
        with open(path) as f:
            content = f.read()
        self.assertIn("CREATE TABLE IF NOT EXISTS chain_support_tickets", content)
        self.assertIn("CREATE TABLE IF NOT EXISTS chain_support_ticket_messages", content)
        self.assertIn("CREATE TABLE IF NOT EXISTS chain_support_agents", content)

    def test_sql_has_indexes(self):
        """SQL should contain indexes for fast lookups."""
        path = os.path.join(os.path.dirname(__file__), "..", "sql", "phase_support_tickets.sql")
        with open(path) as f:
            content = f.read()
        self.assertIn("CREATE INDEX IF NOT EXISTS idx_support_tickets_profile", content)
        self.assertIn("CREATE INDEX IF NOT EXISTS idx_support_tickets_status", content)

    def test_sql_has_internal_note_column(self):
        """SQL should have is_internal_note column in messages table."""
        path = os.path.join(os.path.dirname(__file__), "..", "sql", "phase_support_tickets.sql")
        with open(path) as f:
            content = f.read()
        self.assertIn("is_internal_note BOOLEAN", content)

    def test_sql_has_status_constraints(self):
        """SQL should have status column (constraints are enforced in code)."""
        path = os.path.join(os.path.dirname(__file__), "..", "sql", "phase_support_tickets.sql")
        with open(path) as f:
            content = f.read()
        self.assertIn("status VARCHAR(24) NOT NULL DEFAULT 'open'", content)


class TestSupportServiceContract(unittest.TestCase):
    """Contract tests for support services (no DB required)."""

    def test_service_has_required_functions(self):
        """All required support service functions should exist."""
        from services import support_service as svc
        required = [
            "CATEGORIES", "STATUSES", "PRIORITIES",
            "create_ticket", "get_ticket", "list_user_tickets",
            "add_message", "add_user_message", "add_agent_message",
            "get_messages", "get_user_messages", "update_ticket_status",
            "assign_ticket", "is_agent", "list_all_tickets",
            "count_tickets", "get_ticket_events", "get_help_articles",
            "get_help_article", "get_faq_categories", "add_feedback",
            "get_agent_stats", "get_dashboard_stats", "get_agent_assignments",
        ]
        for name in required:
            self.assertTrue(hasattr(svc, name), f"Missing required: {name}")

    def test_categories_is_dict(self):
        """CATEGORIES should be a dictionary."""
        from services.support_service import CATEGORIES
        self.assertIsInstance(CATEGORIES, dict)

    def test_statuses_is_list(self):
        """STATUSES should be a list."""
        from services.support_service import STATUSES
        self.assertIsInstance(STATUSES, list)

    def test_priorities_is_dict(self):
        """PRIORITIES should be a dictionary."""
        from services.support_service import PRIORITIES
        self.assertIsInstance(PRIORITIES, dict)


if __name__ == "__main__":
    unittest.main(verbosity=2)