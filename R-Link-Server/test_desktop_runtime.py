"""Runtime control is scoped to the desktop instance that started the process."""
import asyncio
from types import SimpleNamespace
import unittest
from fastapi import FastAPI, HTTPException
from starlette.requests import Request
from desktop_runtime import configure_runtime, SERVICE


class DesktopRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.server = SimpleNamespace(should_exit=False)
        configure_runtime(self.app, self.server, "owned-session")
        self.endpoints = {route.path: route.endpoint for route in self.app.routes}

    def test_health_identifies_product_and_desktop_instance(self):
        result = asyncio.run(self.endpoints["/rbox/health"]())
        self.assertEqual(result, {"status": "healthy", "service": SERVICE, "session": "owned-session"})

    def test_shutdown_rejects_another_instance(self):
        request = Request({"type": "http", "headers": [(b"x-rbox-session", b"other-instance")]})
        with self.assertRaises(HTTPException) as error:
            asyncio.run(self.endpoints["/rbox/shutdown"](request))
        self.assertEqual(error.exception.status_code, 403)
        self.assertFalse(self.server.should_exit)

    def test_shutdown_of_owned_instance_requests_graceful_exit(self):
        request = Request({"type": "http", "headers": [(b"x-rbox-session", b"owned-session")]})
        asyncio.run(self.endpoints["/rbox/shutdown"](request))
        self.assertTrue(self.server.should_exit)


if __name__ == "__main__":
    unittest.main()
