"""Flask extensions — 避免循环导入"""
import os

from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="memory://",
    default_limits=[os.environ.get("RATE_LIMIT_DEFAULT", "60/minute")],
)
