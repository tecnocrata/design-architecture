import logging
import os

from dotenv import load_dotenv
from quart import Quart, current_app
from langchain_openai import ChatOpenAI

from .chat_ui import chat_ui_bp
from .chat_api import chat_api_bp
from .tools import get_all_tools
from .vector_store_manager import initialize_vector_store as init_chroma_vector_store
from .agent_builder import create_agent_graph
from .storage import ConversationStorage, InMemoryConversationStorage

def create_app():
    # We do this here in addition to gunicorn.conf.py, since we don't always use gunicorn
    load_dotenv(override=True)
    if os.getenv("RUNNING_IN_PRODUCTION"):
        logging.basicConfig(level=logging.WARNING)
    else:
        logging.basicConfig(level=logging.DEBUG)

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
    """Initializes Langchain resources before the app starts serving.
    This includes loading API keys, initializing the ChatOpenAI model,
    the vector store, tools, and the LangGraph agent.
    """
    logger = logging.getLogger("quart.app")
    logger.info("Initializing Langchain and LangGraph resources...")

    load_dotenv()
    api_key = os.getenv("OPENAI_KEY")
    if not api_key:
        logger.error("OPENAI_KEY not found in environment variables.")
        return

    try:
        # Initialize Conversation Storage
        current_app.conversation_storage = InMemoryConversationStorage()
        logger.info("InMemoryConversationStorage initialized.")

        # Initialize ChatOpenAI model
        chat_model = ChatOpenAI(model="gpt-4", temperature=0, streaming=True, api_key=api_key)
        current_app.chat_model = chat_model
        logger.info("ChatOpenAI model initialized.")

        # Initialize Chroma vector store
        vector_store = init_chroma_vector_store(embeddings_api_key=api_key)
        if vector_store:
            current_app.vector_store = vector_store
            logger.info("Chroma vector store initialized.")
            retriever = vector_store.as_retriever(
                search_type="similarity_score_threshold",
                search_kwargs={"k": 3, "score_threshold": 0.01}
            )
            current_app.vector_store_retriever = retriever
            logger.info("Retriever initialized.")
        else:
            logger.warning("Chroma vector store initialization failed.")
            current_app.vector_store = None
            current_app.vector_store_retriever = None

        # Initialize tools
        tools = get_all_tools(current_app.vector_store_retriever)
        current_app.tools = tools
        logger.info(f"Tools initialized: {len(tools)} tool(s) loaded: {[tool.name for tool in tools]}.")

        # Create and compile the LangGraph Agent
        if not current_app.chat_model:
            logger.error("Chat model not available for agent graph creation.")
            return
        
        compiled_graph = create_agent_graph(current_app.chat_model, current_app.tools or [])
        current_app.compiled_graph = compiled_graph
        logger.info("LangGraph agent created and compiled.")

        # Remove old agent executor if it exists
        if hasattr(current_app, 'agent_executor'):
            delattr(current_app, 'agent_executor')
            logger.info("Removed old 'agent_executor' from current_app.")

    except Exception as e:
        logger.error(f"Error during Langchain/LangGraph resource initialization: {e}", exc_info=True)

async def _cleanup_langchain_resources():
    """Cleans up resources."""
    logger = logging.getLogger("quart.app")
    logger.info("Cleaning up resources...")
    if hasattr(current_app, 'chat_model'):
        delattr(current_app, 'chat_model')
    if hasattr(current_app, 'compiled_graph'):
        delattr(current_app, 'compiled_graph')
    if hasattr(current_app, 'conversation_storage'):
        delattr(current_app, 'conversation_storage')
    logger.info("Resources cleaned up.")
