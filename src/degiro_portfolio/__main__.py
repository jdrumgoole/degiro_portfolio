"""Allow running the package with python -m degiro_portfolio."""
import sys
import uvicorn
from .config import Config


def main():
    """Start the DEGIRO Portfolio web server."""
    uvicorn.run(
        "degiro_portfolio.main:app",
        host=Config.HOST,
        port=Config.PORT,
    )


if __name__ == "__main__":
    sys.exit(main())
