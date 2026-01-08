"""Pytest configuration for comfy-http-webhook tests.

This conftest.py sets up mocks for ComfyUI dependencies and prevents
the main package's __init__.py from being imported during tests.
"""

import sys
import os

# ============================================================================
# CRITICAL: Setup mocks BEFORE any imports from the package
# ============================================================================

# Add the package root to the path
package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if package_root not in sys.path:
    sys.path.insert(0, package_root)


# Mock ComfyUI dependencies
class MockFolderPaths:
    """Mock folder_paths module."""
    @staticmethod
    def get_output_directory():
        return "/tmp/comfy_output"

    @staticmethod
    def get_temp_directory():
        return "/tmp/comfy_temp"

    @staticmethod
    def get_input_directory():
        return "/tmp/comfy_input"


# Mock execution module
class MockPromptQueue:
    currently_running = {}

    def task_done(self, *args, **kwargs):
        pass


class MockExecution:
    PromptQueue = MockPromptQueue


# Register mocks
sys.modules['folder_paths'] = MockFolderPaths()
sys.modules['execution'] = MockExecution()


# Block the main __init__.py from being imported
# This is necessary because it tries to import nodes which have ComfyUI dependencies
class BlockedModule:
    """A module placeholder that blocks imports."""
    def __getattr__(self, name):
        raise ImportError(f"Module blocked for testing: {name}")


# We need to prevent pytest from trying to import the parent __init__.py
# The trick is to put a dummy module in place
import types
parent_package_name = os.path.basename(package_root)

# Create a minimal mock module for the parent package that doesn't import nodes
mock_parent = types.ModuleType(parent_package_name)
mock_parent.__path__ = [package_root]
mock_parent.__file__ = os.path.join(package_root, '__init__.py')

# Only register if not already present (to avoid overwriting real module in some cases)
if parent_package_name not in sys.modules:
    sys.modules[parent_package_name] = mock_parent


def pytest_configure(config):
    """Configure pytest before tests run."""
    os.environ['COMFY_WEBHOOK_TEST_MODE'] = '1'


def pytest_unconfigure(config):
    """Clean up after tests."""
    if 'COMFY_WEBHOOK_TEST_MODE' in os.environ:
        del os.environ['COMFY_WEBHOOK_TEST_MODE']
