import logging
import os

from dotenv import load_dotenv
from quart import Quart, current_app
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from .chat_ui import chat_ui_bp
from .chat_api import chat_api_bp
from .config import AGENT_SYSTEM_PROMPT
from .tools import get_all_tools
from .vector_store_manager import initialize_vector_store as init_chroma_vector_store

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
    """Initializes Langchain resources before the app starts serving.
    This includes loading API keys, initializing the ChatOpenAI model,
    the vector store, and the agent executor.
    """
    logger = logging.getLogger("quart.app")
    logger.info("Initializing Langchain resources...")

    # Load environment variables (especially OPENAI_KEY)
    load_dotenv()
    api_key = os.getenv("OPENAI_KEY")
    if not api_key:
        logger.error("OPENAI_KEY not found in environment variables.")
        return

    try:
        # Initialize ChatOpenAI model
        chat_model = ChatOpenAI(model="gpt-4", temperature=0, streaming=True, api_key=api_key)
        current_app.chat_model = chat_model
        logger.info("ChatOpenAI model initialized.")

        # Initialize Chroma vector store using the new manager
        # Pass the API key needed for OpenAIEmbeddings within initialize_vector_store
        vector_store = init_chroma_vector_store(embeddings_api_key=api_key)
        if vector_store:
            current_app.vector_store = vector_store
            logger.info("Chroma vector store initialized via vector_store_manager.")
            # retriever = vector_store.as_retriever(search_kwargs={"k": 3}) # DON'T DELETE THIS LINE
            retriever = vector_store.as_retriever(
                search_type="similarity_score_threshold",
                search_kwargs={"k": 3, "score_threshold": 0.01}  # Adjusted threshold
            )
            current_app.vector_store_retriever = retriever
            logger.info(f"Retriever initialized with search_type='similarity_score_threshold' and score_threshold=0.01, k=3.")
        else:
            logger.warning("Chroma vector store initialization failed. See previous errors from vector_store_manager.")
            current_app.vector_store = None
            current_app.vector_store_retriever = None

        # Initialize tools
        tools = get_all_tools(current_app.vector_store_retriever) # Pass the retriever to the tool function
        current_app.tools = tools
        logger.info(f"Tools initialized: {len(tools)} tool(s) loaded.")

        # Create Agent Prompt Template
        agent_prompt_template = ChatPromptTemplate.from_messages(
            [
                ("system", AGENT_SYSTEM_PROMPT),
                MessagesPlaceholder(variable_name="chat_history", optional=True),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )
        current_app.agent_prompt_template = agent_prompt_template
        logger.info("Agent prompt template created.")

        # Create Agent
        if not current_app.chat_model:
            logger.error("Chat model not available for agent creation.")
            return
        # Agent can be created with an empty list of tools if retriever failed
        agent = create_openai_tools_agent(current_app.chat_model, current_app.tools or [], agent_prompt_template)
        current_app.agent = agent
        logger.info("Agent created.")

        # Create Agent Executor
        agent_executor = AgentExecutor(agent=agent, tools=current_app.tools or [], verbose=True) # Set verbose=False for production
        current_app.agent_executor = agent_executor
        logger.info("Agent Executor created and ready.")

    except Exception as e:
        logger.error(f"Error during Langchain resource initialization: {e}", exc_info=True)

async def _cleanup_langchain_resources():
    """Shuts down the LangChain chat model if it exists on current_app."""
    if hasattr(current_app, 'chat_model'):
        current_app.logger.info("Cleaning up LangChain chat model.")
        # LangChain models don't require explicit cleanup
        delattr(current_app, 'chat_model')
    else:
        current_app.logger.info("No LangChain chat model to clean up.")
