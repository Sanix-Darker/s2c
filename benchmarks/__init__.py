"""s2c benchmarks.

Run with::

    python -m benchmarks.profile            # all scenarios, synthetic inputs
    python -m benchmarks.profile --scenario ascii --trials 10
    python -m benchmarks.profile --with-camera    # opt-in real hardware

Writes a JSON summary to stdout (and optionally to ``--out``) so Future-Phase-2
results can diff cleanly against today's baseline.
"""
