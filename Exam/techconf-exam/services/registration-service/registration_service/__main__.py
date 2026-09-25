"""Registration service entry point for `python -m registration_service`."""

from registration_service import create_app

app = create_app()

if __name__ == "__main__":
    from registration_service.config import config
    app.run(host="0.0.0.0", port=config.port)