import json
import logging
from quart import (
    Blueprint,
    render_template,
    request,
    Response,
    current_app,
    stream_with_context,
    jsonify,
)
from .storage import InMemoryConversationStorage
from langchain.schema import HumanMessage, SystemMessage, AIMessage
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain.chains import RetrievalQA
from langchain_openai import ChatOpenAI
import os
from .config import SYSTEM_PROMPT_TEMPLATE, VECTORE_STORE_PROMPT_TEMPLATE

# Define the Blueprint for the chat UI and API
# It will look for templates in a 'templates' folder in the same directory as this blueprint.
chat_ui_bp = Blueprint(
    "chat_ui", __name__, template_folder="templates"
)

# Configure a logger for this blueprint
logger = logging.getLogger(__name__)

# Initialize storage
storage = InMemoryConversationStorage()

def initialize_vector_store():
    """Initialize the vector store with movie data."""
    try:
        # Load the movies text file
        loader = TextLoader("src/myapp/movies.txt", encoding="utf-8")
        documents = loader.load()

        # Split the text into chunks
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        docs = text_splitter.split_documents(documents)

        # Initialize embeddings
        embeddings = OpenAIEmbeddings(
            openai_api_key=os.getenv("OPENAI_KEY"),
            model="text-embedding-3-small"
        )

        # Create and return the vector store
        return Chroma.from_documents(docs, embeddings)
    except Exception as e:
        logger.error(f"Error initializing vector store: {e}")
        return None

# Initialize vector store when the blueprint is created
vector_store = initialize_vector_store()

@chat_ui_bp.route("/")
async def index():
    """Serves the main chat HTML page."""
    logger.info("Serving chat.html")
    show_multimodal_features = current_app.config.get("SHOW_MULTIMODAL_FEATURES", False)
    return await render_template("chat.html", show_multimodal_features=show_multimodal_features)

@chat_ui_bp.post("/conversations")
async def create_conversation():
    """Create a new conversation and return its ID."""
    try:
        conversation_id = await storage.create_conversation()
        return jsonify({"conversation_id": conversation_id})
    except Exception as e:
        logger.error(f"Error creating conversation: {e}")
        return jsonify({"error": "Failed to create conversation"}), 500

@chat_ui_bp.get("/conversations/<conversation_id>")
async def get_conversation(conversation_id: str):
    """Get a conversation by ID."""
    try:
        conversation = await storage.get_conversation(conversation_id)
        if not conversation:
            return jsonify({"error": "Conversation not found"}), 404
        
        messages = await storage.get_messages(conversation_id)
        return jsonify({
            "id": conversation.id,
            "created_at": conversation.created_at.isoformat(),
            "updated_at": conversation.updated_at.isoformat(),
            "messages": messages
        })
    except Exception as e:
        logger.error(f"Error getting conversation: {e}")
        return jsonify({"error": "Failed to get conversation"}), 500

@chat_ui_bp.post("/chat/stream")
async def handle_chat_post():
    """
    Handles POST requests for chat messages.
    Receives messages, stores them, and returns a confirmation.
    The actual SSE stream is handled by a separate GET endpoint.
    """
    chat_model = getattr(current_app, 'chat_model', None)
    model_name = getattr(current_app, 'model_name', None)

    if not chat_model or not model_name:
        logger.error("LangChain chat model or model name not configured on the current_app.")
        return jsonify({"error": "Server configuration error."}), 500

    if not vector_store:
        logger.error("Vector store not initialized.")
        return jsonify({"error": "Vector store not available."}), 500

    try:
        request_json = await request.get_json()
        if not request_json:
            logger.warning("Received empty JSON body for POST /chat/stream.")
            return jsonify({"error": "Invalid request: No JSON body."}), 400
    except Exception as e:
        logger.error(f"Error parsing request JSON for POST /chat/stream: {e}")
        return jsonify({"error": f"Invalid JSON format: {e}"}), 400

    session_state = request_json.get("sessionState", {})
    conversation_id = session_state.get("conversation_id")
    if not conversation_id:
        logger.warning("Missing 'conversation_id' in session_state for POST /chat/stream.")
        return jsonify({"error": "Invalid request: 'conversation_id' is required in session_state."}), 400

    request_messages = request_json.get("messages", [])
    context_data = request_json.get("context", {})
    image_base64_data_uri = context_data.get("file")
    show_multimodal_features = current_app.config.get("SHOW_MULTIMODAL_FEATURES", False)

    user_message_stored = False
    if request_messages:
        user_message_input = request_messages[-1]["content"]
        user_message_content_to_store = ""

        if isinstance(user_message_input, list):  # Multimodal content
            user_message_content_to_store = next((part.get("text") for part in user_message_input if part.get("type") == "text"), "")
            if not user_message_content_to_store and image_base64_data_uri and show_multimodal_features:
                user_message_content_to_store = "[Image received]"
        elif isinstance(user_message_input, str):  # Simple text content
            user_message_content_to_store = user_message_input
        
        if user_message_content_to_store:
            await storage.add_message(conversation_id, "user", user_message_content_to_store)
            user_message_stored = True
            logger.info(f"User message stored for conversation '{conversation_id}'.")
        elif show_multimodal_features and image_base64_data_uri: 
            # This case handles if user_message_input was a list, but only contained an image part,
            # and image_base64_data_uri was also sent in context.
            await storage.add_message(conversation_id, "user", "[Image received]")
            user_message_stored = True
            logger.info(f"User image placeholder (from multimodal list) stored for conversation '{conversation_id}'.")

    elif show_multimodal_features and image_base64_data_uri: # Only image in context, no "messages" array or empty "messages"
        await storage.add_message(conversation_id, "user", "[Image received]")
        user_message_stored = True
        logger.info(f"User image placeholder (from context) stored for conversation '{conversation_id}'.")
    
    if not user_message_stored:
        logger.warning(f"No storable message content (text or image) found in POST /chat/stream for conversation '{conversation_id}'.")
        return jsonify({"error": "No message content (text or image) provided in the request."}), 400

    return jsonify({"status": "message_received", "conversation_id": conversation_id})

@chat_ui_bp.get("/chat/stream")
async def handle_chat_get_stream():
    """
    Handles GET requests for chat messages using Server-Sent Events (SSE).
    Retrieves conversation history, calls the LangChain API with RAG,
    and streams the response back as SSE events.
    """
    chat_model = getattr(current_app, 'chat_model', None)
    model_name = getattr(current_app, 'model_name', None)

    if not chat_model or not model_name:
        logger.error("LangChain chat model or model name not configured for GET /chat/stream.")
        return Response("data: {\"error\": \"Server configuration error.\"}\n\n", 
                       status=500, 
                       content_type="text/event-stream")

    if not vector_store:
        logger.error("Vector store not initialized for GET /chat/stream.")
        return Response("data: {\"error\": \"Vector store not available.\"}\n\n", 
                       status=500, 
                       content_type="text/event-stream")

    conversation_id = request.args.get("conversation_id")
    if not conversation_id:
        logger.warning("Missing 'conversation_id' in GET /chat/stream request.")
        return Response("data: {\"error\": \"Invalid request: 'conversation_id' is required.\"}\n\n", 
                      status=400, 
                      content_type="text/event-stream")
    
    messages = await storage.get_messages(conversation_id)
    # sse_generator will handle if messages is None or empty.

    @stream_with_context
    async def sse_generator():
        try:
            logger.debug(f"SSE Generator for '{conversation_id}': Starting. Messages count: {len(messages) if messages else 0}.")

            last_user_message_text_content = None
            if messages: # Ensure messages is not None and not empty
                for msg in reversed(messages): # Iterate in reverse to find the last user message
                    if msg.get("role") == "user":
                        content = msg.get("content")
                        if isinstance(content, list):  # Multimodal content
                            text_part = next((part.get("text") for part in content if part.get("type") == "text"), None)
                            if text_part: # Prioritize text part for RAG
                                last_user_message_text_content = text_part
                                break
                        elif isinstance(content, str):  # Simple text content
                            last_user_message_text_content = content
                            break
            
            if not last_user_message_text_content:
                logger.info(f"No text content found in the last user message for RAG query (conversation '{conversation_id}'). Will proceed without RAG context if applicable.")

            qa_chain = RetrievalQA.from_chain_type(
                llm=chat_model,
                chain_type="stuff",
                retriever=vector_store.as_retriever(search_kwargs={"k": 3})
            )
            
            context_response_text = ""
            if last_user_message_text_content: # Only query RAG if we have text
                logger.info(f"Performing RAG query for '{conversation_id}' with: '{last_user_message_text_content[:50]}...'")
                try:
                    # Use ainvoke for async compatibility
                    context_response = await qa_chain.ainvoke({"query": last_user_message_text_content})
                    if context_response and "result" in context_response and context_response["result"]:
                        context_response_text = context_response["result"]
                        logger.info(f"Context retrieved for '{conversation_id}'. ... {context_response_text[:50]}...")
                    else:
                        logger.info(f"No context retrieved for '{conversation_id}'.")
                except Exception as rag_e:
                    logger.error(f"RAG query failed for '{conversation_id}': {rag_e}", exc_info=True)
                    # Optionally yield an error specific to RAG failure or just proceed without context
            else:
                logger.info(f"Skipping RAG query for '{conversation_id}' as no last user text message content was found.")

            # Build the system message using the SYSTEM_PROMPT_TEMPLATE and inject context/question
            system_message_content = SYSTEM_PROMPT_TEMPLATE.format(
                context=context_response_text or "",
                question=last_user_message_text_content or ""
            )
            langchain_messages = [SystemMessage(content=system_message_content)]
            if messages: # Ensure messages is not None
                for msg in messages:
                    role = msg.get("role")
                    content = msg.get("content") # This can be string or list for multimodal

                    if role == "user":
                        langchain_messages.append(HumanMessage(content=content))
                    elif role == "assistant":
                        langchain_messages.append(AIMessage(content=content))

            full_response = ""
            async for chunk in chat_model.astream(langchain_messages):
                if chunk.content:
                    full_response += chunk.content
                    event_dict = {
                        "choices": [{
                            "delta": {"content": chunk.content},
                            "finish_reason": None 
                        }]
                    }
                    yield f"data: {json.dumps(event_dict, ensure_ascii=False)}\n\n"

            if full_response:
                await storage.add_message(conversation_id, "assistant", full_response)
                logger.info(f"Assistant response for '{conversation_id}' stored.")
            else:
                logger.info(f"No content generated by LLM for '{conversation_id}'.")

            final_event_payload = {
                "event": "complete", 
                "conversation_id": conversation_id,
                 # To mimic OpenAI, send a final choice with finish_reason
                "choices": [{"delta": {}, "finish_reason": "stop"}]
            }
            yield f"data: {json.dumps(final_event_payload, ensure_ascii=False)}\n\n"
            logger.info(f"SSE stream complete for conversation '{conversation_id}'.")

        except Exception as e:
            logger.error(f"SSE generation failed for '{conversation_id}': {e}", exc_info=True)
            error_payload = {
                "error": {
                    "message": str(e),
                    "type": type(e).__name__
                }
            }
            try:
                yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n"
            except Exception as yield_e: # Catch errors during yielding the error itself
                logger.error(f"Failed to yield error payload for '{conversation_id}': {yield_e}")

    return Response(
        sse_generator(),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable proxy buffering
        }
    )
