from quart import Blueprint, jsonify, redirect, render_template, request, url_for, current_app, Response, stream_with_context
import json
import logging
import asyncio
from langchain.schema import HumanMessage, SystemMessage, AIMessage

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
    chat_model = getattr(current_app, 'chat_model', None)
    model_name = getattr(current_app, 'model_name', None)

    if not chat_model or not model_name:
        logger.error("LangChain chat model or model name not configured on current_app for /api/chat.")
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
        logger.debug(f"Sending to LangChain (non-stream) for /api/chat: {messages}")
        # Convert messages to LangChain message format
        langchain_messages = []
        for msg in messages:
            if msg["role"] == "user":
                langchain_messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                langchain_messages.append(AIMessage(content=msg["content"]))
            elif msg["role"] == "system":
                langchain_messages.append(SystemMessage(content=msg["content"]))

        # Get response from LangChain
        response = await chat_model.ainvoke(langchain_messages)
        return jsonify({"reply": response.content})

    except Exception as e:
        logger.error(f"LangChain API call failed for /api/chat: {e}", exc_info=True)
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
    chat_model = getattr(current_app, 'chat_model', None)
    model_name = getattr(current_app, 'model_name', None)

    if not chat_model or not model_name:
        logger.error("LangChain chat model or model name not configured on current_app for /api/chat-stream.")
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
            logger.debug(f"Sending to LangChain (stream) for /api/chat-stream: {messages}")
            # Convert messages to LangChain message format
            langchain_messages = []
            for msg in messages:
                if msg["role"] == "user":
                    langchain_messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    langchain_messages.append(AIMessage(content=msg["content"]))
                elif msg["role"] == "system":
                    langchain_messages.append(SystemMessage(content=msg["content"]))

            async for chunk in chat_model.astream(langchain_messages):
                if chunk.content:
                    yield json.dumps({"choices": [{"delta": {"content": chunk.content}}]}, ensure_ascii=False) + "\n"

        except Exception as e:
            logger.error(f"LangChain API call failed for /api/chat-stream: {e}", exc_info=True)
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
    chat_model = getattr(current_app, 'chat_model', None)
    model_name = getattr(current_app, 'model_name', None)

    if not chat_model or not model_name:
        logger.error("LangChain chat model or model name not configured on current_app for /api/chat-sse.")
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
            logger.debug(f"Sending to LangChain (SSE) for /api/chat-sse: {messages}")
            # Convert messages to LangChain message format
            langchain_messages = []
            for msg in messages:
                if msg["role"] == "user":
                    langchain_messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    langchain_messages.append(AIMessage(content=msg["content"]))
                elif msg["role"] == "system":
                    langchain_messages.append(SystemMessage(content=msg["content"]))

            async for chunk in chat_model.astream(langchain_messages):
                if chunk.content:
                    # Format as SSE event
                    yield f"data: {json.dumps({'choices': [{'delta': {'content': chunk.content}}]}, ensure_ascii=False)}\n\n"
                
                # Add a small delay to prevent overwhelming the client
                await asyncio.sleep(0.01)
        
        except Exception as e:
            logger.error(f"LangChain API call failed for /api/chat-sse: {e}", exc_info=True)
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
