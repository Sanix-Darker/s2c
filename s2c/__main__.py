"""Console-script entry: `s2c [-s ...] [-c ...] [-i ...] [-p ...]`.

Replaces the previous (broken) `s2c = s2c.main:main` mapping in
`pyproject.toml`. All CLI parsing is delegated to `s2c.cli_args` so the
`python -m client.main` legacy entry stays in lock-step.
"""

from __future__ import annotations

from s2c.cli_args import build_parser, parse_session
from client.main import Client


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    session = parse_session(args)
    client = Client(session)
    client.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
