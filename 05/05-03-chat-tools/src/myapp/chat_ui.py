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
from langchain.schema import HumanMessage, AIMessage

# Define the Blueprint for the chat UI and API
chat_ui_bp = Blueprint(
    "chat_ui", __name__, template_folder="templates"
)

# Configure a logger for this blueprint
logger = logging.getLogger(__name__)

# Initialize storage
storage = InMemoryConversationStorage()

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
    Agent/LLM interaction does NOT happen here.
    """
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
            await storage.add_message(conversation_id, "user", "[Image received]")
            user_message_stored = True
            logger.info(f"User image placeholder (from multimodal list) stored for conversation '{conversation_id}'.")

    elif show_multimodal_features and image_base64_data_uri: 
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
    Retrieves conversation history, uses the AgentExecutor to get a response,
    and streams the response back as SSE events.
    """
    agent_executor = getattr(current_app, 'agent_executor', None)

    if not agent_executor:
        logger.error("Agent Executor not configured for GET /chat/stream.")
        return Response("data: {\"error\": \"Server agent not available.\"}\n\n",
                       status=500,
                       content_type="text/event-stream")

    conversation_id = request.args.get("conversation_id")
    if not conversation_id:
        logger.warning("Missing 'conversation_id' in GET /chat/stream request.")
        return Response("data: {\"error\": \"Invalid request: 'conversation_id' is required.\"}\n\n", 
                      status=400, 
                      content_type="text/event-stream")
    
    messages = await storage.get_messages(conversation_id)

    @stream_with_context
    async def sse_generator():
        try:
            logger.debug(f"SSE Agent Generator for '{conversation_id}': Starting. Messages count: {len(messages) if messages else 0}.")

            last_user_message_text_content = None
            chat_history_for_agent = []

            if messages: 
                for i, msg in enumerate(messages):
                    role = msg.get("role")
                    content = msg.get("content")

                    if role == "user":
                        chat_history_for_agent.append(HumanMessage(content=content))
                        if i == len(messages) - 1: 
                            if isinstance(content, list):  
                                text_part = next((part.get("text") for part in content if part.get("type") == "text"), None)
                                if text_part:
                                    last_user_message_text_content = text_part
                            elif isinstance(content, str):  
                                last_user_message_text_content = content
                    elif role == "assistant":
                        chat_history_for_agent.append(AIMessage(content=content))
            
            if not last_user_message_text_content:
                logger.warning(f"No last user message text content found for agent input (conversation '{conversation_id}').")
                yield f"data: {json.dumps({'error': 'No user input to process.'}, ensure_ascii=False)}\n\n"
                final_error_event = {"event": "error", "conversation_id": conversation_id, "message": "No user input."}
                yield f"data: {json.dumps(final_error_event, ensure_ascii=False)}\n\n"
                return

            # Remove the last user message from history if it's the same as the input, to avoid duplication
            if chat_history_for_agent and isinstance(chat_history_for_agent[-1], HumanMessage) and chat_history_for_agent[-1].content == last_user_message_text_content:
                chat_history_for_agent = chat_history_for_agent[:-1]

            logger.info(f"Invoking agent for '{conversation_id}' with input: '{last_user_message_text_content[:100]}...'")
            
            full_response = ""
            async for chunk_dict in agent_executor.astream(
                {"input": last_user_message_text_content, "chat_history": chat_history_for_agent}
            ):
                if "output" in chunk_dict and isinstance(chunk_dict["output"], str):
                    content_piece = chunk_dict["output"]
                    if content_piece: # Ensure content_piece is not empty
                        full_response += content_piece
                        event_data = {
                            "choices": [{
                                "delta": {"content": content_piece},
                                "finish_reason": None 
                            }]
                        }
                        yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"

            if full_response:
                await storage.add_message(conversation_id, "assistant", full_response)
                logger.info(f"SSE stream complete for conv '{conversation_id}'. Full response stored.")
            else:
                logger.info(f"SSE stream complete for conv '{conversation_id}'. No response content generated by agent.")

            # Send a final event indicating the end of the stream
            final_event = {"event": "end", "conversation_id": conversation_id}
            yield f"data: {json.dumps(final_event, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.error(f"Error during SSE generation for conversation '{conversation_id}': {e}", exc_info=True)
            error_event = {"error": str(e), "conversation_id": conversation_id}
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
            final_error_event = {"event": "error", "conversation_id": conversation_id, "message": str(e)}
            yield f"data: {json.dumps(final_error_event, ensure_ascii=False)}\n\n"

    return Response(sse_generator(), content_type='text/event-stream')
