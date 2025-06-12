import logging
import os

from dotenv import load_dotenv
from quart import Quart, current_app
import openai
# import azure.identity.aio

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

    # Register the module-level functions as lifecycle hooks
    # These functions will be called within an app context, so current_app is available.
    app.before_serving(_initialize_openai_resources)
    app.after_serving(_cleanup_openai_resources)

    app.register_blueprint(chat_api.chat_api_bp)
    app.register_blueprint(chat_ui.chat_ui_bp)

    return app

# --- Helper functions defined at module level ---
async def _initialize_openai_resources():
    """Configures and initializes the OpenAI client and attaches it to current_app."""
    openai_host = os.getenv("OPENAI_HOST", "github")
    # Attach model_name and openai_client to the application instance via current_app
    current_app.model_name = os.getenv("OPENAI_MODEL", "gpt-4o")
    current_app.logger.info(f"Selected OpenAI host: {openai_host}, Model: {current_app.model_name}")

    if openai_host == "local":
        current_app.logger.info(
            "Using model %s from local OpenAI-compatible API with no key", current_app.model_name)
        current_app.openai_client = openai.AsyncOpenAI(
            api_key="no-key-required", base_url=os.getenv("LOCAL_OPENAI_ENDPOINT"))
    elif openai_host == "github":
        current_app.logger.info(
            "Using model %s from GitHub models with GITHUB_TOKEN as key", current_app.model_name)
        current_app.openai_client = openai.AsyncOpenAI(
            api_key=os.environ["GITHUB_TOKEN"],
            base_url="https://models.inference.ai.azure.com",
        )
    else:  # openai_host == "openai"
        current_app.logger.info(
            "Using model %s from OpenAI with OPENAI_KEY as key", current_app.model_name)
        current_app.openai_client = openai.AsyncOpenAI(
            api_key=os.environ["OPENAI_KEY"],
            base_url=os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1"),
        )
    # else:  # Azure OpenAI
    #     client_args = {}
    #     if os.getenv("AZURE_OPENAI_KEY_FOR_CHATVISION"):
    #         current_app.logger.info(
    #             "Using model %s from Azure OpenAI with key", current_app.model_name)
    #         client_args["api_key"] = os.getenv("AZURE_OPENAI_KEY_FOR_CHATVISION")
    #     else:
    #         if os.getenv("RUNNING_IN_PRODUCTION"):
    #             client_id = os.getenv("AZURE_CLIENT_ID")
    #             current_app.logger.info(
    #                 "Using model %s from Azure OpenAI with managed identity credential for client ID %s",
    #                 current_app.model_name,
    #                 client_id,
    #             )
    #             azure_credential = azure.identity.aio.ManagedIdentityCredential(client_id=client_id)
    #         else:
    #             tenant_id = os.environ["AZURE_TENANT_ID"]
    #             current_app.logger.info(
    #                 "Using model %s from Azure OpenAI with Azure Developer CLI credential for tenant ID: %s",
    #                 current_app.model_name,
    #                 tenant_id,
    #             )
    #             azure_credential = azure.identity.aio.AzureDeveloperCliCredential(tenant_id=tenant_id)
    #         client_args["azure_ad_token_provider"] = azure.identity.aio.get_bearer_token_provider(
    #             azure_credential, "https://cognitiveservices.azure.com/.default"
    #         )
    #     current_app.openai_client = openai.AsyncAzureOpenAI(
    #         azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    #         api_version=os.getenv("AZURE_OPENAI_API_VERSION") or "2024-05-01-preview",
    #         **client_args,
    #     )

async def _cleanup_openai_resources():
    """Shuts down the OpenAI client if it exists on current_app."""
    if hasattr(current_app, 'openai_client') and current_app.openai_client:
        current_app.logger.info("Shutting down OpenAI client.")
        await current_app.openai_client.close()
    else:
        current_app.logger.info("No OpenAI client to shut down or already shut down.")
