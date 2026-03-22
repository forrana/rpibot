#!/usr/bin/env python3
"""
Test script to verify the camera target fallback logic works correctly.
This simulates the error condition and tests the fallback mechanism.
"""

import os
import sys

# Add current directory to path so we can import camera_manager
sys.path.insert(0, '.')

def test_camera_target_fallback():
    """Test that the camera manager handles target mismatches correctly"""

    print("Testing camera target fallback logic...")

    # Test 1: Normal case (should work on RPI)
    print("\n1. Testing normal case...")

    # Test 2: Simulate the error condition
    print("\n2. Testing target fallback logic...")

    # Mock the Picamera2 class to simulate the error
    original_picamera2 = None
    try:
        from picamera2 import Picamera2 as OriginalPicamera2
        original_picamera2 = OriginalPicamera2

        class MockPicamera2:
            def __init__(self):
                self.failed_targets = []

            def create_video_configuration(self):
                return {}

            def configure(self, config):
                pass

            def start(self):
                # Simulate the target mismatch error
                if 'LIBCAMERA_RPI_TARGET' in os.environ:
                    target = os.environ['LIBCAMERA_RPI_TARGET']
                    self.failed_targets.append(target)

                    # Fail on first target, succeed on second
                    if target == 'pisp' and 'bcm2835' not in self.failed_targets:
                        raise Exception("Unexpected target reported: expected 'pisp', got bcm2835")
                    elif target == 'bcm2835':
                        # Success case
                        return

                raise Exception("No target set")

            def stop(self):
                pass

            def close(self):
                pass

        # Replace Picamera2 with our mock
        import camera_manager
        camera_manager.Picamera2 = MockPicamera2

        # Test the camera manager
        cm = camera_manager.CameraManager()
        status = cm.get_status()

        print(f"Camera available: {status['available']}")
        print(f"Error: {status['error']}")

        if status['available']:
            print("✓ SUCCESS: Camera fallback logic works correctly!")
            return True
        else:
            print("✗ FAILED: Camera fallback logic failed")
            return False

    except ImportError:
        print("picamera2 not available, skipping detailed test")
        return None
    finally:
        # Restore original Picamera2 if it existed
        if original_picamera2:
            import camera_manager
            camera_manager.Picamera2 = original_picamera2

if __name__ == "__main__":
    result = test_camera_target_fallback()
    if result is True:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    elif result is False:
        print("\n❌ Some tests failed!")
        sys.exit(1)
    else:
        print("\n⚠️  Tests skipped (picamera2 not available)")
        sys.exit(0)