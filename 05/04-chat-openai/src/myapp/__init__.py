import logging
import os

from dotenv import load_dotenv
from quart import Quart


def create_app():
    # We do this here in addition to gunicorn.conf.py, since we don't always use gunicorn
    load_dotenv(override=True)
    if os.getenv("RUNNING_IN_PRODUCTION"):
        logging.basicConfig(level=logging.WARNING)
    else:
        logging.basicConfig(level=logging.INFO)

    from . import chat_api
    from . import chat_ui
    app = Quart(__name__)

    app.register_blueprint(chat_api.chat_api_bp)
    app.register_blueprint(chat_ui.chat_ui_bp)

    return app