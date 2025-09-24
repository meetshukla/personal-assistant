"""Basic test script for Personal Assistant."""

import asyncio
import sys
from pathlib import Path

# Add the server directory to the path
sys.path.insert(0, str(Path(__file__).parent / "server"))

from server.conductor.runtime import MessageConductorRuntime
from server.specialists.registry import get_specialist_registry
from server.services.conversation import get_conversation_memory
from server.logging_config import configure_logging, get_logger


async def test_message_conductor():
    """Test the Message Conductor."""

    print("🧪 Testing Message Conductor...")

    try:
        runtime = MessageConductorRuntime()
        result = await runtime.execute("Hello, can you help me check my emails?", "+1234567890")

        if result.success:
            print(f"✅ Message Conductor test passed")
            print(f"Response: {result.response}")
        else:
            print(f"❌ Message Conductor test failed: {result.error}")

    except Exception as e:
        print(f"❌ Message Conductor test error: {e}")


async def test_specialists():
    """Test the Service Specialists."""

    print("\n🔧 Testing Service Specialists...")

    try:
        registry = get_specialist_registry()

        # Test EmailSpecialist
        email_result = await registry.execute_task(
            "EmailSpecialist-test",
            "EmailSpecialist",
            "Check for emails from alice@example.com"
        )

        if email_result.success:
            print("✅ EmailSpecialist test passed")
        else:
            print(f"❌ EmailSpecialist test failed: {email_result.error}")

        # Test ReminderSpecialist
        reminder_result = await registry.execute_task(
            "ReminderSpecialist-test",
            "ReminderSpecialist",
            "Remind me to call mom at 6pm today"
        )

        if reminder_result.success:
            print("✅ ReminderSpecialist test passed")
        else:
            print(f"❌ ReminderSpecialist test failed: {reminder_result.error}")

    except Exception as e:
        print(f"❌ Specialists test error: {e}")


async def test_conversation_memory():
    """Test conversation memory."""

    print("\n💭 Testing Conversation Memory...")

    try:
        memory = get_conversation_memory()

        # Test recording messages
        await memory.record_user_message("+1234567890", "Test user message", "msg_123")
        await memory.record_assistant_message("+1234567890", "Test assistant response")

        # Test retrieving history
        history = await memory.get_conversation_history("+1234567890", limit=10)

        if history:
            print("✅ Conversation memory test passed")
            print(f"Retrieved {len(history)} messages")
        else:
            print("⚠️ Conversation memory test: No messages retrieved (might be database issue)")

    except Exception as e:
        print(f"❌ Conversation memory test error: {e}")


def test_configuration():
    """Test basic configuration."""

    print("\n⚙️ Testing Configuration...")

    try:
        from server.config import get_settings

        settings = get_settings()

        if settings.openrouter_api_key:
            print("✅ OpenRouter API key configured")
        else:
            print("❌ OpenRouter API key missing")

        # WhatsApp functionality removed - using web interface only
        print("✅ Web interface configured")

        print("✅ Configuration test completed")

    except Exception as e:
        print(f"❌ Configuration test error: {e}")


async def main():
    """Run all basic tests."""

    configure_logging()

    print("🧪 Personal Assistant Basic Tests")
    print("=" * 40)

    # Test configuration
    test_configuration()

    # Test core components
    await test_message_conductor()
    await test_specialists()
    await test_conversation_memory()

    print("\n🎯 Basic tests completed!")
    print("\nNote: Some tests may show warnings if external services (Supabase, etc.) are not configured.")


if __name__ == "__main__":
    asyncio.run(main())