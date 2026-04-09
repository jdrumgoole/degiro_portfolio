"""Allow running the package with python -m degiro_portfolio."""
import sys
import argparse


def main() -> None:
    """Start the DEGIRO Portfolio application."""
    parser = argparse.ArgumentParser(
        description="DEGIRO Portfolio - Portfolio Visualization Tool",
    )
    parser.add_argument(
        "--desktop", action="store_true",
        help="Launch as a desktop application (requires pywebview)",
    )
    parser.add_argument(
        "--port", type=int, default=None,
        help="Port for the web server (default: 8000)",
    )
    args = parser.parse_args()

    if args.desktop:
        from .desktop import run_desktop
        run_desktop(port=args.port or 8000)
    else:
        import uvicorn
        from .config import Config
        uvicorn.run(
            "degiro_portfolio.main:app",
            host=Config.HOST,
            port=args.port or Config.PORT,
        )


if __name__ == "__main__":
    sys.exit(main())
