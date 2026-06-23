"""s2c — terminal video chat.

Public surface intentionally minimal: the package houses the CLI plumbing
and the shared NDJSON framing helper. The actual client/server logic lives
in `client.main` and `server.main` to preserve the legacy `python -m` entry
points.
"""

__version__ = "0.1.0"
