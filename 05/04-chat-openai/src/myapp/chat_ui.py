import json
import logging
from quart import (
    Blueprint,
    render_template,
    request,
    Response,
    current_app,
    stream_with_context,
)

# Define the Blueprint for the chat UI and API
# It will look for templates in a 'templates' folder in the same directory as this blueprint.
chat_ui_bp = Blueprint(
    "chat_ui", __name__, template_folder="templates"
)

# Configure a logger for this blueprint
logger = logging.getLogger(__name__)


@chat_ui_bp.route("/")
async def index():
    """Serves the main chat HTML page."""
    logger.info("Serving chat.html")
    show_multimodal_features = current_app.config.get("SHOW_MULTIMODAL_FEATURES", False)
    return await render_template("chat.html", show_multimodal_features=show_multimodal_features)


@chat_ui_bp.post("/chat/stream") # Matches the client-side AIChatProtocolClient endpoint
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
        # Return a JSON response that AIChatProtocolClient can parse as an error
        error_response = {"error": "Server configuration error."}
        return Response(
            json.dumps(error_response) + "\n", # Ensure newline for NDJSON
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

    request_messages = request_json.get("messages", [])
    context_data = request_json.get("context", {})
    image_base64_data_uri = context_data.get("file") # Expected to be a data URI (e.g., data:image/png;base64,...)
    show_multimodal_features = current_app.config.get("SHOW_MULTIMODAL_FEATURES", False)

    @stream_with_context
    async def response_stream():
        api_messages = []

        # System message can be added here if desired, or managed by the client
        # api_messages.append({"role": "system", "content": "You are a helpful assistant."})

        # Add existing messages from history (all but the last one, which is the current user query)
        if len(request_messages) > 1:
            api_messages.extend(request_messages[:-1])

        current_user_message_text = request_messages[-1]["content"] if request_messages else ""

        if show_multimodal_features and image_base64_data_uri:
            user_content_parts = [
                {"type": "text", "text": current_user_message_text}
            ]
            # The client sends a full data URI, which is what OpenAI GPT-4o expects.
            user_content_parts.append(
                {
                    "type": "image_url",
                    "image_url": {"url": image_base64_data_uri, "detail": "auto"},
                }
            )
            api_messages.append({"role": "user", "content": user_content_parts})
        elif request_messages: # Text-only message
            api_messages.append(request_messages[-1]) # Add the last user message
        else:
            logger.warning("No messages provided in the request to /chat endpoint.")
            yield json.dumps({"error": "No messages provided in the request."}) + "\n"
            return

        logger.debug(f"Messages to OpenAI: {json.dumps(api_messages)[:500]}...") # Log snippet

        try:
            # Use openai_client and model_name from current_app
            chat_coroutine = openai_client.chat.completions.create(
                model=model_name,
                messages=api_messages,
                stream=True,
                temperature=request_json.get("temperature", 0.7),
                # max_tokens=1500, # Optional: control response length and cost
            )
            async for event in await chat_coroutine:
                event_dict = event.model_dump() # Convert Pydantic model to dict
                # The AIChatProtocolClient expects the 'choices' array with delta/full message.
                # We will send the whole event_dict if it contains choices, or a specific error structure.
                if event_dict.get("choices"):
                    # The client-side SDK handles parsing this structure
                    yield json.dumps(event_dict, ensure_ascii=False) + "\n"
                elif event_dict.get("error"): # Handle error objects if the API streams them
                    logger.error(f"OpenAI API streamed an error: {event_dict['error']}")
                    yield json.dumps({"error": event_dict["error"]}, ensure_ascii=False) + "\n"

        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}", exc_info=True)
            # Ensure the error is in a format the client can understand
            error_payload = {
                "error": {
                    "message": str(e),
                    "type": type(e).__name__
                }
            }
            yield json.dumps(error_payload, ensure_ascii=False) + "\n"

    return Response(response_stream(), content_type="application/x-ndjson")
