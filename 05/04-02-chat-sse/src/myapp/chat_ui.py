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
@chat_ui_bp.get("/chat/stream")
async def chat_handler():
    """
    Handles chat requests from the client using Server-Sent Events (SSE).
    Receives messages and an optional image, calls the OpenAI API,
    and streams the response back as SSE events.
    """
    openai_client = getattr(current_app, 'openai_client', None)
    model_name = getattr(current_app, 'model_name', None)

    if not openai_client or not model_name:
        logger.error("OpenAI client or model name not configured on the current_app.")
        return Response("data: {\"error\": \"Server configuration error.\"}\n\n", 
                       status=500, 
                       content_type="text/event-stream")

    # For GET requests (SSE connection), we don't need to parse the request body
    if request.method == "GET":
        # The actual chat request data should be stored in the session or passed via query parameters
        # For now, we'll use query parameters
        conversation_id = request.args.get("conversation_id")
        if not conversation_id:
            return Response("data: {\"error\": \"Invalid request: 'conversation_id' is required.\"}\n\n", 
                          status=400, 
                          content_type="text/event-stream")
        
        # Get the messages from the conversation
        conversation_messages = await storage.get_messages(conversation_id)
        if not conversation_messages:
            return Response("data: {\"error\": \"No messages found in conversation.\"}\n\n", 
                          status=400, 
                          content_type="text/event-stream")
        
        messages = conversation_messages
    else:
        # For POST requests, parse the JSON body
        try:
            request_json = await request.get_json()
            if not request_json:
                logger.warning("Received empty JSON body.")
                return Response("data: {\"error\": \"Invalid request: No JSON body.\"}\n\n", 
                              status=400, 
                              content_type="text/event-stream")
        except Exception as e:
            logger.error(f"Error parsing request JSON: {e}")
            return Response(f"data: {{\"error\": \"Invalid JSON format: {e}\"}}\n\n", 
                          status=400, 
                          content_type="text/event-stream")

        session_state = request_json.get("sessionState", {})
        logger.info(f"Session state: {session_state}")
        conversation_id = session_state.get("conversation_id")
        if not conversation_id:
            return Response("data: {\"error\": \"Invalid request: 'conversation_id' is required in session_state.\"}\n\n", 
                          status=400, 
                          content_type="text/event-stream")

        request_messages = request_json.get("messages", [])
        context_data = request_json.get("context", {})
        image_base64_data_uri = context_data.get("file")
        show_multimodal_features = current_app.config.get("SHOW_MULTIMODAL_FEATURES", False)

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
            return Response("data: {\"error\": \"No messages provided in the request.\"}\n\n", 
                          status=400, 
                          content_type="text/event-stream")

        messages = conversation_messages

    @stream_with_context
    async def sse_generator():
        try:
            logger.debug(f"Messages to OpenAI: {json.dumps(messages)[:500]}...")

            full_response = ""
            chat_coroutine = openai_client.chat.completions.create(
                model=model_name,
                messages=messages,
                stream=True,
                temperature=0.7,
            )
            
            async for event in await chat_coroutine:
                event_dict = event.model_dump()
                if event_dict.get("choices"):
                    delta = event_dict["choices"][0].get("delta", {})
                    if delta.get("content"):
                        full_response += delta["content"]
                    yield f"data: {json.dumps(event_dict, ensure_ascii=False)}\n\n"
                elif event_dict.get("error"):
                    logger.error(f"OpenAI API streamed an error: {event_dict['error']}")
                    yield f"data: {json.dumps({'error': event_dict['error']}, ensure_ascii=False)}\n\n"

            # Store the complete assistant's reply after streaming is done
            if full_response and request.method == "POST":
                await storage.add_message(conversation_id, "assistant", full_response)

        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}", exc_info=True)
            error_payload = {
                "error": {
                    "message": str(e),
                    "type": type(e).__name__
                }
            }
            yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n"

    return Response(
        sse_generator(),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable proxy buffering
        }
    )
