#!/usr/bin/env python3
"""Startup script for Personal Assistant Web Application."""

import asyncio
import subprocess
import sys
import time
from pathlib import Path

async def start_backend():
    """Start the FastAPI backend server."""
    print("🚀 Starting FastAPI backend server...")

    # Change to project directory
    project_dir = Path(__file__).parent

    try:
        # Start the backend server
        process = subprocess.Popen([
            sys.executable, "run_server.py"
        ], cwd=project_dir)

        print(f"✅ Backend server started (PID: {process.pid})")
        print("📡 Backend running at: http://localhost:8001")

        return process

    except Exception as e:
        print(f"❌ Failed to start backend: {e}")
        return None

def start_frontend():
    """Start the Next.js frontend server."""
    print("🌐 Starting Next.js frontend server...")

    web_dir = Path(__file__).parent / "web"

    try:
        # Start the frontend server
        process = subprocess.Popen([
            "npm", "run", "dev"
        ], cwd=web_dir)

        print(f"✅ Frontend server started (PID: {process.pid})")
        print("🌍 Frontend running at: http://localhost:3000")

        return process

    except Exception as e:
        print(f"❌ Failed to start frontend: {e}")
        return None

async def main():
    """Main startup function."""
    print("🤖 Personal Assistant Web Application")
    print("=" * 50)

    # Start backend
    backend_process = await start_backend()
    if not backend_process:
        print("❌ Cannot start without backend server")
        return

    # Wait a bit for backend to start
    print("⏳ Waiting for backend to initialize...")
    await asyncio.sleep(3)

    # Start frontend
    frontend_process = start_frontend()
    if not frontend_process:
        print("❌ Cannot start frontend server")
        backend_process.terminate()
        return

    print("\n🎉 Personal Assistant is ready!")
    print("-" * 30)
    print("📱 Open your browser and go to: http://localhost:3000 (or the port shown above)")
    print("💬 Try asking: 'Check my emails' or 'Remind me to call mom at 6pm'")
    print("⏹️  Press Ctrl+C to stop both servers")

    try:
        # Keep both processes running
        while True:
            # Check if processes are still running
            if backend_process.poll() is not None:
                print("❌ Backend process stopped")
                break
            if frontend_process.poll() is not None:
                print("❌ Frontend process stopped")
                break

            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("\n🛑 Shutting down servers...")

        # Terminate both processes
        frontend_process.terminate()
        backend_process.terminate()

        # Wait for clean shutdown
        try:
            frontend_process.wait(timeout=5)
            backend_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            frontend_process.kill()
            backend_process.kill()

        print("✅ Servers stopped successfully")

if __name__ == "__main__":
    asyncio.run(main())