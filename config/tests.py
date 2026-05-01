from io import StringIO
from importlib import import_module

from django.core.management import call_command
from django.test import SimpleTestCase


class AsgiConfigurationTests(SimpleTestCase):
    def test_asgi_application_imports_cleanly(self):
        module = import_module("config.asgi")

        self.assertTrue(hasattr(module, "application"))

    def test_websocket_routing_includes_core_and_messaging_paths(self):
        routing = import_module("config.routing")

        patterns = [str(pattern.pattern) for pattern in routing.websocket_urlpatterns]

        self.assertTrue(any("ws/notifications/" in pattern for pattern in patterns))
        self.assertTrue(any("ws/messages/<int:conversation_id>/" in pattern for pattern in patterns))
        self.assertTrue(any("ws/calls/<int:conversation_id>/" in pattern for pattern in patterns))

    def test_notification_and_chat_consumers_import_cleanly(self):
        core_consumers = import_module("core.consumers")
        messaging_consumers = import_module("messaging.consumers")

        self.assertTrue(hasattr(core_consumers, "NotificationConsumer"))
        self.assertTrue(hasattr(messaging_consumers, "ChatConsumer"))
        self.assertTrue(hasattr(messaging_consumers, "CallSignalingConsumer"))

    def test_realtime_status_command_reports_registered_websockets(self):
        out = StringIO()

        call_command("realtime_status", stdout=out)

        output = out.getvalue()
        self.assertIn("ws/notifications/", output)
        self.assertIn("ws/messages/", output)
        self.assertIn("ws/calls/", output)
