"""Shared Flask extension instances.

Extensions are instantiated here without an app so that blueprints can
import them at module level.  The actual app binding happens in
``create_app`` via ``limiter.init_app(app)``.
"""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="memory://",
    default_limits=[],
)
