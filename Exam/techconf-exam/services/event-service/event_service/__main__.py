"""Event service entry point for `python -m event_service`."""

from event_service import create_app

app = create_app()

if __name__ == "__main__":
    from event_service.config import config
    app.run(host="0.0.0.0", port=config.port)