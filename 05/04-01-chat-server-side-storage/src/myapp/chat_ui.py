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

# Define the Blueprint for the chat UI and API
# It will look for templates in a 'templates' folder in the same directory as this blueprint.
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
async def chat_handler():
    """
    Handles chat requests from the client.
    Receives messages and an optional image, calls the OpenAI API,
    and streams the response back in NDJSON format.
    """
    # Access openai_client and model_name from current_app
    openai_client = getattr(current_app, 'openai_client', None)
    model_name = getattr(current_app, 'model_name', None)

    if not openai_client or not model_name:
        logger.error(
            "OpenAI client or model name not configured on the current_app."
        )
        error_response = {"error": "Server configuration error."}
        return Response(
            json.dumps(error_response) + "\n",
            status=500,
            content_type="application/x-ndjson",
        )

    try:
        request_json = await request.get_json()
        if not request_json:
            logger.warning("Received empty JSON body.")
            error_response = {"error": "Invalid request: No JSON body."}
            return Response(
                json.dumps(error_response) + "\n",
                status=400,
                content_type="application/x-ndjson",
            )
    except Exception as e:
        logger.error(f"Error parsing request JSON: {e}")
        error_response = {"error": f"Invalid JSON format: {e}"}
        return Response(
            json.dumps(error_response) + "\n",
            status=400,
            content_type="application/x-ndjson",
        )

    session_state = request_json.get("sessionState", {})
    logger.info(f"Session state!!!: {session_state}")
    conversation_id = session_state.get("conversation_id")
    if not conversation_id:
        error_response = {"error": "Invalid request: 'conversation_id' is required in session_state."}
        return Response(
            json.dumps(error_response) + "\n",
            status=400,
            content_type="application/x-ndjson",
        )

    request_messages = request_json.get("messages", [])
    context_data = request_json.get("context", {})
    image_base64_data_uri = context_data.get("file")
    show_multimodal_features = current_app.config.get("SHOW_MULTIMODAL_FEATURES", False)

    @stream_with_context
    async def response_stream():
        try:
            # Store the user's message
            if request_messages:
                await storage.add_message(conversation_id, "user", request_messages[-1]["content"])

            # Get all messages for the conversation
            conversation_messages = await storage.get_messages(conversation_id)

            if show_multimodal_features and image_base64_data_uri:
                user_content_parts = [
                    {"type": "text", "text": request_messages[-1]["content"] if request_messages else ""}
                ]
                user_content_parts.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": image_base64_data_uri, "detail": "auto"},
                    }
                )
                conversation_messages.append({"role": "user", "content": user_content_parts})
            elif request_messages:
                conversation_messages.append(request_messages[-1])
            else:
                logger.warning("No messages provided in the request to /chat endpoint.")
                yield json.dumps({"error": "No messages provided in the request."}) + "\n"
                return

            logger.debug(f"Messages to OpenAI: {json.dumps(conversation_messages)[:500]}...")

            full_response = ""
            chat_coroutine = openai_client.chat.completions.create(
                model=model_name,
                messages=conversation_messages,
                stream=True,
                temperature=request_json.get("temperature", 0.7),
            )
            async for event in await chat_coroutine:
                event_dict = event.model_dump()
                if event_dict.get("choices"):
                    delta = event_dict["choices"][0].get("delta", {})
                    if delta.get("content"):
                        full_response += delta["content"]
                    yield json.dumps(event_dict, ensure_ascii=False) + "\n"
                elif event_dict.get("error"):
                    logger.error(f"OpenAI API streamed an error: {event_dict['error']}")
                    yield json.dumps({"error": event_dict["error"]}, ensure_ascii=False) + "\n"

            # Store the complete assistant's reply after streaming is done
            if full_response:
                await storage.add_message(conversation_id, "assistant", full_response)

        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}", exc_info=True)
            error_payload = {
                "error": {
                    "message": str(e),
                    "type": type(e).__name__
                }
            }
            yield json.dumps(error_payload, ensure_ascii=False) + "\n"

    return Response(response_stream(), content_type="application/x-ndjson")
