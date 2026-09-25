"""User service entry point for `python -m app`."""

from . import create_app

app = create_app()

if __name__ == "__main__":
    from .config import config
    app.run(host="0.0.0.0", port=config.port)