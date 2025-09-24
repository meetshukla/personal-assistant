#!/usr/bin/env python3
"""
Personal Assistant Setup Script

This script helps you set up the Personal Assistant project quickly.
"""

import os
import sys
import subprocess
from pathlib import Path

def print_step(step_num, description):
    print(f"\n{'='*60}")
    print(f"STEP {step_num}: {description}")
    print(f"{'='*60}")

def run_command(command, description, cwd=None):
    print(f"\n📋 {description}")
    print(f"🔧 Running: {command}")

    try:
        result = subprocess.run(
            command.split(),
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True
        )
        print(f"✅ Success!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {e}")
        print(f"📝 Output: {e.stdout}")
        print(f"⚠️  Error: {e.stderr}")
        return False

def check_requirements():
    """Check if Python and Node.js are installed."""
    print_step(1, "Checking Requirements")

    # Check Python
    try:
        python_version = subprocess.check_output([sys.executable, "--version"], text=True).strip()
        print(f"✅ {python_version}")
    except Exception as e:
        print(f"❌ Python check failed: {e}")
        return False

    # Check Node.js
    try:
        node_version = subprocess.check_output(["node", "--version"], text=True).strip()
        print(f"✅ Node.js {node_version}")
    except FileNotFoundError:
        print("❌ Node.js not found. Please install Node.js 18+ from https://nodejs.org/")
        return False
    except Exception as e:
        print(f"❌ Node.js check failed: {e}")
        return False

    # Check npm
    try:
        npm_version = subprocess.check_output(["npm", "--version"], text=True).strip()
        print(f"✅ npm {npm_version}")
    except Exception as e:
        print(f"❌ npm check failed: {e}")
        return False

    return True

def setup_environment():
    """Set up the environment file."""
    print_step(2, "Setting Up Environment")

    env_file = Path(".env")
    env_example = Path(".env.example")

    if env_file.exists():
        print(f"✅ .env file already exists")
        return True

    if env_example.exists():
        print(f"📝 Copying .env.example to .env")
        env_file.write_text(env_example.read_text())
        print(f"⚠️  Please edit .env with your API keys!")
        print(f"📖 See README.md for configuration details")
        return True
    else:
        print(f"❌ .env.example not found")
        return False

def install_python_deps():
    """Install Python dependencies."""
    print_step(3, "Installing Python Dependencies")

    return run_command(
        f"{sys.executable} -m pip install -r server/requirements.txt",
        "Installing Python packages"
    )

def install_node_deps():
    """Install Node.js dependencies."""
    print_step(4, "Installing Node.js Dependencies")

    return run_command(
        "npm install",
        "Installing Node.js packages",
        cwd="client"
    )

def main():
    """Main setup function."""
    print("🤖 Personal Assistant Setup")
    print("=" * 60)

    # Change to script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)

    # Run setup steps
    if not check_requirements():
        print("\n❌ Requirements check failed. Please install missing dependencies.")
        sys.exit(1)

    if not setup_environment():
        print("\n❌ Environment setup failed.")
        sys.exit(1)

    if not install_python_deps():
        print("\n❌ Python dependencies installation failed.")
        sys.exit(1)

    if not install_node_deps():
        print("\n❌ Node.js dependencies installation failed.")
        sys.exit(1)

    # Success message
    print("\n" + "=" * 60)
    print("🎉 SETUP COMPLETE!")
    print("=" * 60)
    print("\n📋 Next Steps:")
    print("1. Edit .env with your API keys (see README.md)")
    print("2. Run: python start_web.py")
    print("3. Open: http://localhost:3000")
    print("\n🚀 Happy chatting with your personal assistant!")

if __name__ == "__main__":
    main()