"""The diagnostic engine the agent reports on: main.py's collectors, findings
and readiness verdict.

It still lives in main.py, shared with Pulse Diagnostics, until it moves into
its own package (PV-49, a later slice). This package never imports main: in
Diagnostics main.py runs as __main__, and importing it again would load a
second copy of the app. main.py binds itself here at import instead, and the
agent reads the engine through `engine`, attribute by attribute at call time,
so a test that patches main.DEMO_MODE or main.run_ps still takes effect.
"""


class _Engine:
    def __init__(self):
        self._module = None

    def __getattr__(self, name):
        module = self.__dict__.get("_module")
        if module is None:
            raise RuntimeError(f"pulse_agent needs main.py's engine for {name}; import main first")
        return getattr(module, name)


engine = _Engine()


def bind(module) -> None:
    """Called once by main.py, with itself."""
    engine._module = module
