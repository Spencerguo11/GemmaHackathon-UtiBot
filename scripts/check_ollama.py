#!/usr/bin/env python3
"""Check Ollama connectivity."""
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import get_settings
import requests

def check_ollama():
    """Check if Ollama is running and model is available."""
    settings = get_settings()
    
    print(f"Checking Ollama at {settings.ollama_host}...")
    
    try:
        response = requests.get(f"{settings.ollama_host}/api/tags", timeout=5)
        if response.status_code != 200:
            print(f"❌ Ollama returned status {response.status_code}")
            return False
        
        data = response.json()
        models = [m.get("name") for m in data.get("models", [])]
        
        if settings.ollama_model in models:
            print(f"✅ Ollama is running and model '{settings.ollama_model}' is available")
            print(f"   Available models: {', '.join(models)}")
            return True
        else:
            print(f"❌ Model '{settings.ollama_model}' not found")
            print(f"   Available models: {', '.join(models)}")
            print(f"\n   To pull the model, run:")
            print(f"   ollama pull {settings.ollama_model}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to Ollama at {settings.ollama_host}")
        print(f"   Make sure Ollama is running: ollama serve")
        return False
    except Exception as e:
        print(f"❌ Error checking Ollama: {e}")
        return False

if __name__ == "__main__":
    success = check_ollama()
    sys.exit(0 if success else 1)
