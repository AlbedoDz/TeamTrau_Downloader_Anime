import os

from dotenv import load_dotenv

from logger import setup_logger

# Load environment variables from .env file
load_dotenv()

# Initialize the custom logger
logger = setup_logger("main")


def add(a: int, b: int) -> int:
    """Adds two integers and returns the result."""
    logger.debug(f"Adding values: a={a}, b={b}")
    return a + b


def main() -> None:
    """Core entry point."""
    logger.info("Starting the main application...")

    app_env = os.getenv("APP_ENV", "not_set")
    logger.info(f"Environment configuration: APP_ENV={app_env}")

    result = add(10, 32)
    logger.info(f"Computation complete: add(10, 32) = {result}")


if __name__ == "__main__":
    main()
