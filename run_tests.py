"""Test runner for Personal Assistant."""

import asyncio
import os
import sys
from pathlib import Path

# Set up the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set environment variables for testing
os.environ.setdefault("OPENROUTER_API_KEY", "test-key")
# WhatsApp functionality removed - using web interface only

from server.logging_config import configure_logging, get_logger


async def test_imports():
    """Test that all modules can be imported."""

    print("📦 Testing imports...")

    try:
        from server.config import get_settings
        from server.conductor.runtime import MessageConductorRuntime
        from server.specialists.registry import get_specialist_registry
        # WhatsApp import removed - using web interface only

        print("✅ All imports successful")
        return True

    except Exception as e:
        print(f"❌ Import error: {e}")
        return False


async def test_configuration():
    """Test configuration system."""

    print("\n⚙️ Testing Configuration...")

    try:
        from server.config import get_settings

        settings = get_settings()

        # Check that we can access settings
        assert settings.app_name == "Personal Assistant Server"
        assert settings.openrouter_api_key == "test-key"

        print("✅ Configuration test passed")
        return True

    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False


async def test_specialist_registry():
    """Test specialist registry."""

    print("\n🔧 Testing Specialist Registry...")

    try:
        from server.specialists.registry import get_specialist_registry

        registry = get_specialist_registry()

        # Test creating specialists
        email_specialist = registry.get_or_create_specialist("test-email", "EmailSpecialist")
        reminder_specialist = registry.get_or_create_specialist("test-reminder", "ReminderSpecialist")

        assert email_specialist is not None
        assert reminder_specialist is not None
        assert registry.get_specialist_count() == 2

        print("✅ Specialist registry test passed")
        return True

    except Exception as e:
        print(f"❌ Specialist registry test failed: {e}")
        return False


async def test_message_conductor_basic():
    """Test basic Message Conductor functionality."""

    print("\n🧪 Testing Message Conductor (basic)...")

    try:
        from server.conductor.message_conductor import build_conductor_system_prompt

        # Test system prompt loading
        prompt = build_conductor_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 100  # Should be a substantial prompt

        print("✅ Message Conductor basic test passed")
        return True

    except Exception as e:
        print(f"❌ Message Conductor basic test failed: {e}")
        return False


async def main():
    """Run all tests."""

    configure_logging()

    print("🧪 Personal Assistant Test Suite")
    print("=" * 40)

    tests = [
        ("Imports", test_imports),
        ("Configuration", test_configuration),
        ("Specialist Registry", test_specialist_registry),
        ("Message Conductor", test_message_conductor_basic),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        try:
            if await test_func():
                passed += 1
        except Exception as e:
            print(f"❌ Test {test_name} crashed: {e}")

    print(f"\n📊 Test Results: {passed}/{total} passed")

    if passed == total:
        print("🎉 All tests passed! The Personal Assistant is ready to run.")
    else:
        print("⚠️ Some tests failed. Check the output above for details.")


if __name__ == "__main__":
    asyncio.run(main())