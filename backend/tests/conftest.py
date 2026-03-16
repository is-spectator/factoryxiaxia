"""Pytest fixtures — patch SQLAlchemy to use SQLite before importing app."""
import os
import pytest

os.environ["DB_USER"] = "x"
os.environ["DB_PASS"] = "x"
os.environ["DB_HOST"] = "x"
os.environ["DB_NAME"] = "x"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["RATE_LIMIT_DEFAULT"] = "9999/minute"
os.environ["RATE_LIMIT_AUTH"] = "9999/minute"

import flask_sqlalchemy

_orig_init = flask_sqlalchemy.SQLAlchemy.__init__


def _patched_init(self, app=None, **kwargs):
    if app is not None:
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    _orig_init(self, app=app, **kwargs)


flask_sqlalchemy.SQLAlchemy.__init__ = _patched_init

import app as flask_app  # noqa: E402


@pytest.fixture()
def client():
    flask_app.app.config["TESTING"] = True
    with flask_app.app.app_context():
        flask_app.db.create_all()
        yield flask_app.app.test_client()
        flask_app.db.session.remove()
        flask_app.db.drop_all()


@pytest.fixture()
def db():
    return flask_app.db


@pytest.fixture()
def app_module():
    return flask_app
