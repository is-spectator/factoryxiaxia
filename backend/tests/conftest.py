"""Pytest fixtures — patch SQLAlchemy to use SQLite before importing app."""
import os
import pytest

os.environ["DB_USER"] = "x"
os.environ["DB_PASS"] = "x"
os.environ["DB_HOST"] = "x"
os.environ["DB_NAME"] = "x"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["APP_ENV"] = "test"
os.environ["RATE_LIMIT_DEFAULT"] = "9999/minute"
os.environ["RATE_LIMIT_AUTH"] = "9999/minute"
os.environ["AGENT_PROVIDER"] = "rules"
os.environ["KONGKONG_RUNTIME_MODE"] = "mock"
os.environ.pop("DASHSCOPE_API_KEY", None)
os.environ.pop("DASHSCOPE_MODEL", None)

import flask_sqlalchemy
from services.public_api_service import reset_public_api_rate_limits

_orig_init = flask_sqlalchemy.SQLAlchemy.__init__
_orig_init_app = flask_sqlalchemy.SQLAlchemy.init_app


def _patched_init(self, app=None, **kwargs):
    if app is not None:
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    _orig_init(self, app=app, **kwargs)


def _patched_init_app(self, app, **kwargs):
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    return _orig_init_app(self, app, **kwargs)


flask_sqlalchemy.SQLAlchemy.__init__ = _patched_init
flask_sqlalchemy.SQLAlchemy.init_app = _patched_init_app

import app as flask_app  # noqa: E402


@pytest.fixture()
def client():
    flask_app.app.config["TESTING"] = True
    flask_app.app.config["PUBLIC_CHAT_IP_LIMIT_PER_MINUTE"] = 9999
    flask_app.app.config["PUBLIC_CHAT_DEPLOYMENT_LIMIT_PER_MINUTE"] = 9999
    with flask_app.app.app_context():
        reset_public_api_rate_limits()
        flask_app.db.create_all()
        yield flask_app.app.test_client()
        flask_app.db.session.remove()
        flask_app.db.drop_all()
        reset_public_api_rate_limits()


@pytest.fixture()
def db():
    return flask_app.db


@pytest.fixture()
def app_module():
    return flask_app
