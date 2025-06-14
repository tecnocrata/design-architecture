import logging
import os

from dotenv import load_dotenv
from quart import Quart, current_app
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage

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

    # Feature flag for multimodal features
    app.config["SHOW_MULTIMODAL_FEATURES"] = os.getenv("SHOW_MULTIMODAL_FEATURES", "False").lower() == "true"
    app.logger.info(f'Multimodal features enabled: {app.config["SHOW_MULTIMODAL_FEATURES"]}')

    # Register the module-level functions as lifecycle hooks
    # These functions will be called within an app context, so current_app is available.
    app.before_serving(_initialize_langchain_resources)
    app.after_serving(_cleanup_langchain_resources)

    app.register_blueprint(chat_api.chat_api_bp)
    app.register_blueprint(chat_ui.chat_ui_bp)

    return app

# --- Helper functions defined at module level ---
async def _initialize_langchain_resources():
    """Configures and initializes the LangChain chat model and attaches it to current_app."""
    openai_host = os.getenv("OPENAI_HOST", "github")
    # Attach model_name and chat_model to the application instance via current_app
    current_app.model_name = os.getenv("OPENAI_MODEL", "gpt-4")
    current_app.logger.info(f"Selected OpenAI host: {openai_host}, Model: {current_app.model_name}")

    if openai_host == "local":
        current_app.logger.info(
            "Using model %s from local OpenAI-compatible API with no key", current_app.model_name)
        current_app.chat_model = ChatOpenAI(
            model_name=current_app.model_name,
            openai_api_key="no-key-required",
            openai_api_base=os.getenv("LOCAL_OPENAI_ENDPOINT"),
            streaming=True
        )
    elif openai_host == "github":
        current_app.logger.info(
            "Using model %s from GitHub models with GITHUB_TOKEN as key", current_app.model_name)
        current_app.chat_model = ChatOpenAI(
            model_name=current_app.model_name,
            openai_api_key=os.environ["GITHUB_TOKEN"],
            openai_api_base="https://models.inference.ai.azure.com",
            streaming=True
        )
    else:  # openai_host == "openai"
        current_app.logger.info(
            "Using model %s from OpenAI with OPENAI_KEY as key", current_app.model_name)
        current_app.chat_model = ChatOpenAI(
            model_name=current_app.model_name,
            openai_api_key=os.environ["OPENAI_KEY"],
            openai_api_base=os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1"),
            streaming=True
        )

async def _cleanup_langchain_resources():
    """Shuts down the LangChain chat model if it exists on current_app."""
    if hasattr(current_app, 'chat_model'):
        current_app.logger.info("Cleaning up LangChain chat model.")
        # LangChain models don't require explicit cleanup
        delattr(current_app, 'chat_model')
    else:
        current_app.logger.info("No LangChain chat model to clean up.")
