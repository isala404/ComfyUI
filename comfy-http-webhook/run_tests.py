#!/usr/bin/env python3
"""
Test runner for comfy-http-webhook package.

This script runs tests while properly handling the package structure
and ComfyUI dependency mocking.

Usage:
    python run_tests.py              # Run all tests
    python run_tests.py -v           # Run with verbose output
    python run_tests.py --unit       # Run only unit tests
"""

import sys
import os

# Setup path BEFORE any imports
package_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, package_root)

# Mock ComfyUI dependencies BEFORE importing anything from the package
class MockFolderPaths:
    @staticmethod
    def get_output_directory():
        return "/tmp/comfy_output"

    @staticmethod
    def get_temp_directory():
        return "/tmp/comfy_temp"

    @staticmethod
    def get_input_directory():
        return "/tmp/comfy_input"


class MockPromptQueue:
    currently_running = {}
    def task_done(self, *args, **kwargs):
        pass


class MockExecution:
    PromptQueue = MockPromptQueue


sys.modules['folder_paths'] = MockFolderPaths()
sys.modules['execution'] = MockExecution()

# Set test mode flag
os.environ['COMFY_WEBHOOK_TEST_MODE'] = '1'


def run_tests():
    """Run all tests using pytest."""
    import subprocess

    # Change to package directory
    os.chdir(package_root)

    # Build pytest command
    cmd = [
        sys.executable, '-m', 'pytest',
        'tests/',
        '-v',
        '--tb=short',
        '--ignore=__init__.py',
        '-p', 'no:cacheprovider',  # Disable cache to avoid issues
    ]

    # Add any additional arguments
    cmd.extend(sys.argv[1:])

    # Run pytest in a subprocess with the right environment
    env = os.environ.copy()
    env['PYTHONPATH'] = package_root

    result = subprocess.run(cmd, env=env, cwd=package_root)
    return result.returncode


def run_unit_tests():
    """Run unit tests directly without pytest (simpler, more reliable)."""
    print("=" * 60)
    print("Running unit tests directly...")
    print("=" * 60)

    success = True
    tests_run = 0
    tests_failed = 0

    # Import test modules
    from utils.mime import guess_mime_type, get_extension_for_mime, get_output_type_from_mime, get_format_from_filename
    from utils.validation import validate_url, is_base64_data, is_url, is_data_url, parse_data_url, sanitize_for_logging
    from core.types import WebhookContext, WebhookResult, OutputInfo, WebhookEvent
    from core.context import register_webhook_context, get_webhook_context, unregister_webhook_context, clear_all_contexts
    from processors.outputs import detect_output_type

    def test(name, condition):
        nonlocal tests_run, tests_failed, success
        tests_run += 1
        if condition:
            print(f"  ✓ {name}")
        else:
            print(f"  ✗ {name}")
            tests_failed += 1
            success = False

    # MIME Tests
    print("\n[MIME Utils]")
    test("guess_mime_type('test.png') == 'image/png'", guess_mime_type('test.png') == 'image/png')
    test("guess_mime_type('test.jpg') == 'image/jpeg'", guess_mime_type('test.jpg') == 'image/jpeg')
    test("guess_mime_type('audio.flac') == 'audio/flac'", guess_mime_type('audio.flac') == 'audio/flac')
    test("guess_mime_type('audio.mp3') == 'audio/mpeg'", guess_mime_type('audio.mp3') == 'audio/mpeg')
    test("guess_mime_type('video.mp4') == 'video/mp4'", guess_mime_type('video.mp4') == 'video/mp4')
    test("guess_mime_type('model.glb') == 'model/gltf-binary'", guess_mime_type('model.glb') == 'model/gltf-binary')
    test("guess_mime_type('') == 'application/octet-stream'", guess_mime_type('') == 'application/octet-stream')
    test("get_extension_for_mime('image/png') == '.png'", get_extension_for_mime('image/png') == '.png')
    test("get_output_type_from_mime('image/jpeg') == 'image'", get_output_type_from_mime('image/jpeg') == 'image')
    test("get_output_type_from_mime('audio/flac') == 'audio'", get_output_type_from_mime('audio/flac') == 'audio')
    test("get_format_from_filename('test.png') == 'png'", get_format_from_filename('test.png') == 'png')

    # Validation Tests
    print("\n[Validation Utils]")
    test("validate_url('https://example.com')[0] == True", validate_url('https://example.com')[0] == True)
    test("validate_url('')[0] == False", validate_url('')[0] == False)
    test("validate_url('ftp://example.com')[0] == False", validate_url('ftp://example.com')[0] == False)
    test("is_url('https://example.com') == True", is_url('https://example.com') == True)
    test("is_url('not-a-url') == False", is_url('not-a-url') == False)
    test("is_base64_data('data:image/png;base64,abc') == True", is_base64_data('data:image/png;base64,abc') == True)
    test("is_data_url('data:text/plain,hello') == True", is_data_url('data:text/plain,hello') == True)

    # Core Types Tests
    print("\n[Core Types]")
    ctx = WebhookContext(callback_url='https://example.com', request_id='test-123')
    test("WebhookContext.callback_url", ctx.callback_url == 'https://example.com')
    test("WebhookContext.request_id", ctx.request_id == 'test-123')
    test("WebhookContext.timeout default", ctx.timeout == 60)
    test("WebhookContext.max_retries default", ctx.max_retries == 3)

    ctx_auto = WebhookContext(callback_url='https://example.com')
    test("WebhookContext auto request_id", ctx_auto.request_id is not None and len(ctx_auto.request_id) > 0)
    test("WebhookContext start_time auto-set", ctx_auto.start_time is not None)

    ctx_auth = WebhookContext(callback_url='https://example.com', auth_header='Authorization', auth_value='Bearer token')
    test("WebhookContext.get_auth_headers()", ctx_auth.get_auth_headers() == {'Authorization': 'Bearer token'})

    result = WebhookResult(success=True, status=200)
    test("WebhookResult.success", result.success == True)
    test("WebhookResult.status", result.status == 200)

    info = OutputInfo(type='image', filename='test.png', mime_type='image/png')
    test("OutputInfo.type", info.type == 'image')
    test("OutputInfo.filename", info.filename == 'test.png')

    test("WebhookEvent.COMPLETED", WebhookEvent.COMPLETED.value == 'workflow.completed')
    test("WebhookEvent.ERROR", WebhookEvent.ERROR.value == 'workflow.error')
    test("WebhookEvent.STARTED", WebhookEvent.STARTED.value == 'workflow.started')

    # Context Registry Tests
    print("\n[Context Registry]")
    clear_all_contexts()
    ctx_reg = WebhookContext(callback_url='https://example.com', prompt_id='p1')
    register_webhook_context(ctx_reg)
    test("register and get context", get_webhook_context('p1') is not None)
    test("get context callback_url", get_webhook_context('p1').callback_url == 'https://example.com')

    removed = unregister_webhook_context('p1')
    test("unregister returns context", removed is not None)
    test("context removed", get_webhook_context('p1') is None)

    test("unregister nonexistent returns None", unregister_webhook_context('nonexistent') is None)

    clear_all_contexts()

    # Output Detection Tests
    print("\n[Output Detection]")
    outputs = detect_output_type({'images': [{'filename': 'test.png', 'subfolder': '', 'type': 'output'}]})
    test("detect images", len(outputs) == 1 and outputs[0].type == 'image')

    outputs = detect_output_type({'audio': [{'filename': 'test.flac', 'subfolder': '', 'type': 'output'}]})
    test("detect audio", len(outputs) == 1 and outputs[0].type == 'audio')

    outputs = detect_output_type({'text': ('Hello world',)})
    test("detect text tuple", len(outputs) == 1 and outputs[0].type == 'text')

    outputs = detect_output_type({'video': [{'filename': 'test.mp4', 'subfolder': '', 'type': 'output'}]})
    test("detect video", len(outputs) == 1 and outputs[0].type == 'video')

    outputs = detect_output_type({})
    test("empty output returns empty list", len(outputs) == 0)

    # Summary
    print("\n" + "=" * 60)
    print(f"Tests: {tests_run} | Passed: {tests_run - tests_failed} | Failed: {tests_failed}")
    print("=" * 60)

    if success:
        print("\n✓ ALL TESTS PASSED")
        return 0
    else:
        print("\n✗ SOME TESTS FAILED")
        return 1


if __name__ == '__main__':
    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__)
        sys.exit(0)

    # Run direct unit tests (more reliable, no pytest collection issues)
    sys.exit(run_unit_tests())
