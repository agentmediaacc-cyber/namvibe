from importlib import import_module

from django.test import SimpleTestCase


class AsgiConfigurationTests(SimpleTestCase):
    def test_asgi_application_imports_cleanly(self):
        module = import_module("config.asgi")

        self.assertTrue(hasattr(module, "application"))
