"""bad_tool evil module — intentionally contains policy violations for testing.

DO NOT deploy this. This fixture exists solely to test the security scanner.
"""
# noqa: S603, S101, S404
import pickle  # forbidden: pickle import
import socket  # forbidden: socket import
import subprocess
import os
import yaml  # type: ignore[import-untyped]


def dangerous_deserialize(data: bytes):
    """Forbidden: pickle.loads usage."""
    return pickle.loads(data)  # noqa: S301


def dangerous_shell(cmd: str) -> str:
    """Forbidden: subprocess with shell=True."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)  # noqa: S602
    return result.stdout


def dangerous_system(cmd: str) -> int:
    """Forbidden: os.system usage."""
    return os.system(cmd)  # noqa: S605


def dangerous_eval(expr: str):
    """Forbidden: eval usage."""
    return eval(expr)  # noqa: S307


def dangerous_exec(code: str) -> None:
    """Forbidden: exec usage."""
    exec(code)  # noqa: S102


def dangerous_yaml_load(stream: str) -> object:
    """Forbidden: yaml.load without SafeLoader."""
    return yaml.load(stream)  # noqa: S506


def debug_logging_example() -> None:
    """Warning: logging at DEBUG level."""
    import logging
    logging.basicConfig(level=logging.DEBUG)
