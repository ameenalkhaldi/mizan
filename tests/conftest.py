"""Shared fixtures for irab tests."""

import sys
import os
import pytest

# Add mcp-server to path so we can import analyzer and server modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mcp-server"))


@pytest.fixture(scope="session")
def analyzer():
    """Buckwalter analyzer instance (expensive, shared across session)."""
    import pyaramorph
    return pyaramorph.Analyzer()


@pytest.fixture(scope="session")
def analyzer_module():
    """Import the analyzer module (pure parsing logic + data)."""
    import analyzer
    return analyzer


@pytest.fixture(scope="session")
def server_module():
    """Import the server module (MCP tools, imports analyzer)."""
    import server
    return server


@pytest.fixture(scope="session")
def disambiguator_module():
    """Import the disambiguator module (deterministic Pass 1)."""
    import disambiguator
    return disambiguator


@pytest.fixture(scope="session")
def classify(disambiguator_module):
    """Shorthand for classify_sentence."""
    return disambiguator_module.classify_sentence


@pytest.fixture(scope="session")
def governor_module():
    """Import the governor module (deterministic Pass 2)."""
    import governor
    return governor
