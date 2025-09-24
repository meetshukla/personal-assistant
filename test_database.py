#!/usr/bin/env python3
"""Simple test script to check if Supabase tables are working."""

import os
import sys
from pathlib import Path

# Add the server directory to the path
sys.path.insert(0, str(Path(__file__).parent / "server"))

try:
    # Import what we need
    from supabase import create_client, Client
    from config import get_settings

    def test_database():
        """Test database connection and tables."""
        print("🔍 Testing Supabase database connection...")

        settings = get_settings()

        if not settings.supabase_url or not settings.supabase_key:
            print("❌ Supabase credentials not configured")
            return False

        try:
            # Create Supabase client
            supabase: Client = create_client(settings.supabase_url, settings.supabase_key)
            print("✅ Supabase client created")

            # Test conversations table
            try:
                result = supabase.table('conversations').select('id').limit(1).execute()
                print("✅ conversations table exists and is accessible")
            except Exception as e:
                print(f"❌ conversations table error: {e}")
                return False

            # Test reminders table
            try:
                result = supabase.table('reminders').select('id').limit(1).execute()
                print("✅ reminders table exists and is accessible")
            except Exception as e:
                print(f"❌ reminders table error: {e}")
                return False

            print("\n🎉 Database is properly configured!")
            return True

        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            return False

    if __name__ == "__main__":
        success = test_database()
        sys.exit(0 if success else 1)

except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're in the virtual environment: source venv/bin/activate")
    sys.exit(1)