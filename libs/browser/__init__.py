# -*- coding: utf-8 -*-
"""
=============================================================================
  CBR AGENTS - BROWSER AUTOMATION PACKAGE
=============================================================================
"""

from libs.browser.interfaces import (
    IBrowserDriver,
    IBrowserSessionManager,
    IExecutionObserver
)
from libs.browser.driver_local import LocalBrowserDriver
from libs.browser.driver_remote import RemoteWSBrowserDriver
from libs.browser.factory import BrowserDriverFactory, BrowserDriverProxy
from libs.browser.session import LocalBrowserSessionManager
from libs.browser.observers import (
    DatabaseExecutionObserver,
    ConsoleExecutionObserver,
    NullExecutionObserver,
    ObserverRegistry
)
from libs.browser.engine import BrowserTools, inspect_dom

__all__ = [
    "IBrowserDriver",
    "IBrowserSessionManager",
    "IExecutionObserver",
    "LocalBrowserDriver",
    "RemoteWSBrowserDriver",
    "BrowserDriverFactory",
    "BrowserDriverProxy",
    "LocalBrowserSessionManager",
    "DatabaseExecutionObserver",
    "ConsoleExecutionObserver",
    "NullExecutionObserver",
    "ObserverRegistry",
    "BrowserTools",
    "inspect_dom"
]
