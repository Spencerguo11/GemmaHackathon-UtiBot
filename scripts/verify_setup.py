#!/usr/bin/env python3
"""
Quick verification of project setup.
Run this after installing dependencies to verify everything is configured correctly.
"""
import sys
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def check_structure():
    """Verify project structure."""
    print("\n📁 Checking Project Structure...")
    
    required_dirs = [
        "config", "models", "ingestion", "services", "database",
        "workflows", "browser", "agents", "mock_providers", "scripts",
        "tests", "data"
    ]
    
    required_files = [
        "app.py", "README.md", "requirements.txt", ".env.example",
        ".gitignore", "pyproject.toml"
    ]
    
    all_good = True
    for dir_name in required_dirs:
        dir_path = project_root / dir_name
        if dir_path.exists() and dir_path.is_dir():
            print(f"  ✅ {dir_name}/")
        else:
            print(f"  ❌ {dir_name}/ MISSING")
            all_good = False
    
    for file_name in required_files:
        file_path = project_root / file_name
        if file_path.exists() and file_path.is_file():
            print(f"  ✅ {file_name}")
        else:
            print(f"  ❌ {file_name} MISSING")
            all_good = False
    
    return all_good


def check_imports():
    """Verify key imports work."""
    print("\n📦 Checking Imports...")
    
    imports_to_check = [
        ("config", "get_settings"),
        ("models", "Bill"),
        ("ingestion", "extract_pdfs_from_zip"),
        ("services", "OllamaClient"),
        ("database", "init_db"),
    ]
    
    all_good = True
    for module_name, class_name in imports_to_check:
        try:
            module = __import__(module_name, fromlist=[class_name])
            if hasattr(module, class_name):
                print(f"  ✅ {module_name}.{class_name}")
            else:
                print(f"  ⚠️  {module_name}.{class_name} (import exists, but symbol not found)")
        except ImportError as e:
            print(f"  ❌ {module_name}.{class_name}: {e}")
            all_good = False
    
    return all_good


def check_env():
    """Check .env configuration."""
    print("\n⚙️  Checking Environment Configuration...")
    
    env_file = project_root / ".env"
    env_example = project_root / ".env.example"
    
    if env_file.exists():
        print(f"  ✅ .env file exists")
    else:
        if env_example.exists():
            print(f"  ⚠️  .env not found, but .env.example exists")
            print(f"     Run: cp .env.example .env")
        else:
            print(f"  ❌ Neither .env nor .env.example found")
    
    if env_example.exists():
        print(f"  ✅ .env.example exists")
    else:
        print(f"  ❌ .env.example missing")


def main():
    """Run all checks."""
    print("=" * 60)
    print("🔌 Utility Coordinator AI - Project Verification")
    print("=" * 60)
    
    struct_ok = check_structure()
    check_env()
    
    # Don't check imports if there are import errors
    try:
        imports_ok = check_imports()
    except Exception as e:
        print(f"\n⚠️  Import check skipped: {e}")
        imports_ok = False
    
    print("\n" + "=" * 60)
    if struct_ok and imports_ok:
        print("✅ Project structure verified successfully!")
        print("\nNext steps:")
        print("  1. python scripts/initialize_db.py")
        print("  2. python scripts/check_ollama.py")
        print("  3. streamlit run app.py")
    else:
        print("⚠️  Some checks failed. See details above.")
    
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
