"""Pytest configuration for comfy-http-webhook tests."""

import sys
import os

# Add the package root to the path for test discovery
package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if package_root not in sys.path:
    sys.path.insert(0, package_root)

# Prevent the main __init__.py from being imported
# (it tries to import nodes which have complex dependencies)
sys.modules['__init__'] = None
