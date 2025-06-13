from quart import Blueprint, jsonify, redirect, render_template, request, url_for, current_app, Response, stream_with_context
import json
import logging
import asyncio

# Configure a logger for this blueprint
logger = logging.getLogger(__name__)

chat_api_bp = Blueprint("chat_api", __name__, url_prefix="/api") # , template_folder="templates", static_folder="static"


# ---------- REST endpoint ----------
@chat_api_bp.get("/hello")
async def hello_api():
    """
    Simple JSON endpoint:
    GET /api/hello  ->  {"message": "Hello from Quart!"}
    """
    return jsonify({"message": "Hello from Quart!"})


# ---------- New Non-Streaming Chat Endpoint ----------
@chat_api_bp.post("/chat")
async def handle_chat():
    """
    Handles non-streaming chat requests.
    Expects a JSON body with a "messages" array.
    Returns a JSON response with the assistant's reply.
    """
    openai_client = getattr(current_app, 'openai_client', None)
    model_name = getattr(current_app, 'model_name', None)

    if not openai_client or not model_name:
        logger.error("OpenAI client or model name not configured on current_app for /api/chat.")
        return jsonify({"error": "Server configuration error."}), 500

    try:
        request_json = await request.get_json()
        if not request_json:
            return jsonify({"error": "Invalid request: No JSON body."}), 400
    except Exception as e:
        logger.error(f"Error parsing request JSON for /api/chat: {e}")
        return jsonify({"error": f"Invalid JSON format: {e}"}), 400

    messages = request_json.get("messages")
    if not messages or not isinstance(messages, list):
        return jsonify({"error": "Invalid request: 'messages' array is required."}), 400

    # For future enhancement: Consider incorporating user_id or session management here
    # to maintain conversation history per user.

    try:
        logger.debug(f"Sending to OpenAI (non-stream) for /api/chat: {messages}")
        completion = await openai_client.chat.completions.create(
            model=model_name,
            messages=messages,
            stream=False,
            temperature=request_json.get("temperature", 0.7),
        )
        
        # Assuming we want to return the content of the first choice's message
        if completion.choices and completion.choices[0].message:
            reply_content = completion.choices[0].message.content
            # For a more complete response, you could return the whole choice or message object
            # For example: completion.choices[0].message.model_dump()
            return jsonify({"reply": reply_content})
        else:
            logger.error("OpenAI response did not contain expected choices or message for /api/chat.")
            return jsonify({"error": "Failed to get a valid response from AI."}), 500

    except Exception as e:
        logger.error(f"OpenAI API call failed for /api/chat: {e}", exc_info=True)
        # Be cautious about exposing raw error messages from external services to the client
        return jsonify({"error": "An error occurred while communicating with the AI service."}), 500


# ---------- New Streaming Chat Endpoint ----------
@chat_api_bp.post("/chat-stream")
async def handle_chat_stream():
    """
    Handles streaming chat requests.
    Expects a JSON body with a "messages" array.
    Streams responses back as NDJSON.
    """
    openai_client = getattr(current_app, 'openai_client', None)
    model_name = getattr(current_app, 'model_name', None)

    if not openai_client or not model_name:
        logger.error("OpenAI client or model name not configured on current_app for /api/chat-stream.")
        error_response = {"error": "Server configuration error."}
        return Response(json.dumps(error_response) + "\n", status=500, content_type="application/x-ndjson")

    try:
        request_json = await request.get_json()
        if not request_json:
            error_response = {"error": "Invalid request: No JSON body."}
            return Response(json.dumps(error_response) + "\n", status=400, content_type="application/x-ndjson")
    except Exception as e:
        logger.error(f"Error parsing request JSON for /api/chat-stream: {e}")
        error_response = {"error": f"Invalid JSON format: {e}"}
        return Response(json.dumps(error_response) + "\n", status=400, content_type="application/x-ndjson")

    messages = request_json.get("messages")
    if not messages or not isinstance(messages, list):
        error_response = {"error": "Invalid request: 'messages' array is required."}
        return Response(json.dumps(error_response) + "\n", status=400, content_type="application/x-ndjson")

    # For future enhancement: Consider incorporating user_id or session management here.

    @stream_with_context
    async def response_stream_generator():
        try:
            logger.debug(f"Sending to OpenAI (stream) for /api/chat-stream: {messages}")
            chat_coroutine = openai_client.chat.completions.create(
                model=model_name,
                messages=messages,
                stream=True,
                temperature=request_json.get("temperature", 0.7),
            )
            async for event in await chat_coroutine:
                event_dict = event.model_dump()
                if event_dict.get("choices"):
                    yield json.dumps(event_dict, ensure_ascii=False) + "\n"
                elif event_dict.get("error"):
                    logger.error(f"OpenAI API streamed an error for /api/chat-stream: {event_dict['error']}")
                    yield json.dumps({"error": event_dict["error"]}, ensure_ascii=False) + "\n"
        
        except Exception as e:
            logger.error(f"OpenAI API call failed for /api/chat-stream: {e}", exc_info=True)
            error_payload = {
                "error": {
                    "message": "An error occurred while communicating with the AI service.",
                    "type": type(e).__name__
                }
            }
            yield json.dumps(error_payload, ensure_ascii=False) + "\n"

    return Response(response_stream_generator(), content_type="application/x-ndjson")


# ---------- SSE Chat Endpoint ----------
@chat_api_bp.post("/chat-sse")
async def handle_chat_sse():
    """
    Handles chat requests using Server-Sent Events (SSE).
    Expects a JSON body with a "messages" array.
    Streams responses back as SSE events.
    """
    openai_client = getattr(current_app, 'openai_client', None)
    model_name = getattr(current_app, 'model_name', None)

    if not openai_client or not model_name:
        logger.error("OpenAI client or model name not configured on current_app for /api/chat-sse.")
        return Response("data: {\"error\": \"Server configuration error.\"}\n\n", 
                       status=500, 
                       content_type="text/event-stream")

    try:
        request_json = await request.get_json()
        if not request_json:
            return Response("data: {\"error\": \"Invalid request: No JSON body.\"}\n\n", 
                          status=400, 
                          content_type="text/event-stream")
    except Exception as e:
        logger.error(f"Error parsing request JSON for /api/chat-sse: {e}")
        return Response(f"data: {{\"error\": \"Invalid JSON format: {e}\"}}\n\n", 
                       status=400, 
                       content_type="text/event-stream")

    messages = request_json.get("messages")
    if not messages or not isinstance(messages, list):
        return Response("data: {\"error\": \"Invalid request: 'messages' array is required.\"}\n\n", 
                       status=400, 
                       content_type="text/event-stream")

    @stream_with_context
    async def sse_generator():
        try:
            logger.debug(f"Sending to OpenAI (SSE) for /api/chat-sse: {messages}")
            chat_coroutine = openai_client.chat.completions.create(
                model=model_name,
                messages=messages,
                stream=True,
                temperature=request_json.get("temperature", 0.7),
            )
            
            async for event in await chat_coroutine:
                event_dict = event.model_dump()
                if event_dict.get("choices"):
                    # Format as SSE event
                    yield f"data: {json.dumps(event_dict, ensure_ascii=False)}\n\n"
                elif event_dict.get("error"):
                    logger.error(f"OpenAI API streamed an error for /api/chat-sse: {event_dict['error']}")
                    yield f"data: {json.dumps({'error': event_dict['error']}, ensure_ascii=False)}\n\n"
                
                # Add a small delay to prevent overwhelming the client
                await asyncio.sleep(0.01)
        
        except Exception as e:
            logger.error(f"OpenAI API call failed for /api/chat-sse: {e}", exc_info=True)
            error_payload = {
                "error": {
                    "message": "An error occurred while communicating with the AI service.",
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
