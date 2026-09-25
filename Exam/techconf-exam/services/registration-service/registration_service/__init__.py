"""Registration service Flask application factory."""

from flask import Flask

from techconf_common import error_response, NOT_FOUND, METHOD_NOT_ALLOWED

from registration_service.config import config
from registration_service.repository import create_registration_repository
from registration_service.routes import bp as registrations_bp
from registration_service.client import create_user_service_client, create_event_service_client


def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)

    # Store config and repository in app config
    app.config["config"] = config
    app.config["repository"] = create_registration_repository(config)
    app.config["user_client"] = create_user_service_client()
    app.config["event_client"] = create_event_service_client()

    # Register blueprints
    app.register_blueprint(registrations_bp)

    # Health endpoint
    @app.route("/health")
    def health():
        return {"status": "ok", "service": "registration-service"}

    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        return error_response(NOT_FOUND, "Not found", status=404)

    @app.errorhandler(405)
    def method_not_allowed(e):
        return error_response(METHOD_NOT_ALLOWED, "Method not allowed", status=405)

    @app.errorhandler(500)
    def internal_error(e):
        return error_response("INTERNAL_ERROR", "Internal server error", status=500)

    # Cleanup on teardown
    @app.teardown_appcontext
    def close_repository(exception):
        repository = app.config.get("repository")
        if repository and hasattr(repository, "close"):
            repository.close()

    return app