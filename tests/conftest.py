"""Pytest fixtures for the Zon Forecast integration."""

from __future__ import annotations

import pycares
import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(scope="session", autouse=True)
def pycares_shutdown_thread():
    """Start pycares' daemon before Home Assistant snapshots threads.

    The mocked aiohttp session still builds an aiodns resolver. pycares then
    starts ``_run_safe_shutdown_loop``, which the Home Assistant test plugin
    treats as a leaked thread if it appears during a test.
    """
    pycares._shutdown_manager.start()


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load custom integrations under custom_components/."""
    return
