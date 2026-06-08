import os

from dotenv import load_dotenv

from downloader.cli import main as run_cli
from logger import setup_logger

# Load environment variables from .env file
load_dotenv()

# Initialize the custom logger
logger = setup_logger("main")


def main() -> None:
    """Core entry point."""
    logger.info("Starting the main application...")

    app_env = os.getenv("APP_ENV", "not_set")
    logger.info(f"Environment configuration: APP_ENV={app_env}")

    # Delegate to the downloader CLI
    run_cli()


if __name__ == "__main__":
    main()
