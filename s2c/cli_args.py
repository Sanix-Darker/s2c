"""Shared CLI parser for s2c.

Both `s2c` (the new package entry) and `python -m client.main` (the legacy
module entry) build their argument list through `build_parser()`. The dict
returned by `parse_session()` matches exactly what `Client.__init__` expects,
so both call-sites stay in sync.
"""

from __future__ import annotations

import argparse
from hashlib import md5
from random import randint
from uuid import uuid1, uuid4


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 2938


def generate_key(args_key: str | None) -> str:
    """Generate the session key. Mirrors the original client behaviour.

    Note: in Phase 1, `-k` is accepted and propagated through the session dict
    but it is *not* used on the wire (transport is unencrypted). The parameter
    is preserved so future crypto phases can adopt it without a CLI break.
    """
    if args_key:
        return args_key
    entropy = str(randint(0, 99_999)) + str(uuid4())
    return "s2c_" + md5(entropy.encode()).hexdigest()[:4]


def parse_session(args: argparse.Namespace) -> dict:
    """Translate CLI args into the dict shape `Client.__init__` expects."""
    return {
        "session_id": str(uuid1()) if args.session_id is None else args.session_id,
        "session_key": generate_key(args.key),
        "client_id": str(uuid4()) if args.client_id is None else args.client_id,
        "ip": args.ip,
        "port": int(args.port),
    }


def build_parser(prog: str = "s2c") -> argparse.ArgumentParser:
    """Build the canonical argparse parser used by both entry points."""
    parser = argparse.ArgumentParser(prog=prog)
    parser.add_argument(
        "-s",
        "--session_id",
        help="The session_id; auto-generated if omitted.",
        type=str,
        default=None,
    )
    parser.add_argument(
        "-c",
        "--client_id",
        help="Your id or name in the session; auto-generated if omitted.",
        type=str,
        default=None,
    )
    parser.add_argument(
        "-k",
        "--key",
        help=(
            "Reserved for future encryption options. Accepted silently in "
            "this release; not used on the wire yet."
        ),
        type=str,
        default=None,
    )
    parser.add_argument(
        "-i",
        "--ip",
        help="Host of the S2C server.",
        type=str,
        default=DEFAULT_HOST,
    )
    parser.add_argument(
        "-p",
        "--port",
        help="Port the S2C server is listening on.",
        type=int,
        default=DEFAULT_PORT,
    )
    return parser
