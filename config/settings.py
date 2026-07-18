"""Application settings from environment variables."""
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    """Main application settings."""

    # Ollama configuration
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "gemma4:e4b"

    # Database
    database_url: str = "sqlite:///data/utility.db"

    # Validation thresholds
    min_confidence: float = 0.85
    high_amount_review_threshold: float = 1000.0

    # ZIP and file limits
    max_zip_files: int = 25
    max_uncompressed_mb: int = 100

    # Browser automation
    max_browser_steps: int = 15

    # Debug mode
    debug: bool = False

    # Web UI
    web_host: str = "0.0.0.0"
    web_port: int = 8080

    class Config:
        env_file = ".env"
        case_sensitive = False


def get_settings() -> Settings:
    """Get settings instance."""
    return Settings()


# Get project root
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
JOBS_DIR = DATA_DIR / "jobs"
SCREENSHOTS_DIR = DATA_DIR / "screenshots"
RECEIPTS_DIR = DATA_DIR / "receipts"

# Ensure directories exist
for directory in [DATA_DIR, JOBS_DIR, SCREENSHOTS_DIR, RECEIPTS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)
