import logging
import json
from quart import Blueprint, request, jsonify, Response, current_app, stream_with_context
from .storage import InMemoryConversationStorage
from langchain.schema import HumanMessage, AIMessage

chat_api_bp = Blueprint("chat_api", __name__, url_prefix="/api")  # Added url_prefix="/api"
logger = logging.getLogger(__name__)
storage = InMemoryConversationStorage()

@chat_api_bp.route("/chat", methods=["POST"])
async def handle_chat():
    """
    Handles non-streaming chat requests using the AgentExecutor.
    """
    agent_executor = getattr(current_app, 'agent_executor', None)
    if not agent_executor:
        logger.error("Agent Executor not configured for /chat POST.")
        return jsonify({"error": "Server agent not available."}), 500

    try:
        data = await request.get_json()
        if not data or "messages" not in data or not data["messages"]:
            return jsonify({"error": "Invalid request: 'messages' are required."}), 400

        request_messages = data["messages"]
        conversation_id = data.get("conversation_id")

        last_user_message_content = None
        chat_history_for_agent = []

        if conversation_id:
            stored_messages = await storage.get_messages(conversation_id)
            if stored_messages:
                for msg_data in stored_messages:
                    role = msg_data.get("role")
                    content = msg_data.get("content")
                    if role == "user":
                        chat_history_for_agent.append(HumanMessage(content=content))
                    elif role == "assistant":
                        chat_history_for_agent.append(AIMessage(content=content))

        for i, msg_data in enumerate(request_messages):
            role = msg_data.get("role")
            content = msg_data.get("content")
            if role == "user":
                if i == len(request_messages) - 1:
                    last_user_message_content = content
                else:
                    chat_history_for_agent.append(HumanMessage(content=content))
            elif role == "assistant":
                chat_history_for_agent.append(AIMessage(content=content))

        if not last_user_message_content:
            return jsonify({"error": "No user input message found in the request."}), 400

        logger.info(f"Invoking agent (non-stream) for conv '{conversation_id}' with input: '{last_user_message_content[:100]}...'")
        
        response = await agent_executor.ainvoke(
            {"input": last_user_message_content, "chat_history": chat_history_for_agent}
        )

        assistant_response_content = response.get("output", "")

        if conversation_id:
            await storage.add_message(conversation_id, "user", last_user_message_content)
            await storage.add_message(conversation_id, "assistant", assistant_response_content)

        return jsonify({"response": assistant_response_content, "conversation_id": conversation_id})

    except Exception as e:
        logger.error(f"Error in /chat POST: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@chat_api_bp.route("/chat-stream", methods=["POST"])  # Changed route from /chat/stream to /chat-stream
async def handle_chat_stream_post():
    """
    Handles streaming chat requests (NDJSON) using the AgentExecutor.
    Accessible at /api/chat-stream
    """
    agent_executor = getattr(current_app, 'agent_executor', None)
    if not agent_executor:
        logger.error("Agent Executor not configured for /chat-stream POST.")
        return Response(
            json.dumps({"error": "Server agent not available."}), 
            status=500, 
            mimetype="application/x-ndjson"
        )

    try:
        data = await request.get_json()
        if not data or "messages" not in data or not data["messages"]:
            return Response(
                json.dumps({"error": "Invalid request: 'messages' are required."}),
                status=400,
                mimetype="application/x-ndjson"
            )

        request_messages = data["messages"]
        conversation_id = data.get("conversation_id")

        last_user_message_content = None
        chat_history_for_agent = []
        if conversation_id:
            stored_messages = await storage.get_messages(conversation_id)
            if stored_messages:
                for msg_data in stored_messages:
                    role, content = msg_data.get("role"), msg_data.get("content")
                    if role == "user": chat_history_for_agent.append(HumanMessage(content=content))
                    elif role == "assistant": chat_history_for_agent.append(AIMessage(content=content))
        
        for i, msg_data in enumerate(request_messages):
            role, content = msg_data.get("role"), msg_data.get("content")
            if role == "user":
                if i == len(request_messages) - 1: last_user_message_content = content
                else: chat_history_for_agent.append(HumanMessage(content=content))
            elif role == "assistant": chat_history_for_agent.append(AIMessage(content=content))

        if not last_user_message_content:
            return Response(json.dumps({"error": "No user input message found."}), status=400, mimetype="application/x-ndjson")

        logger.info(f"Invoking agent (NDJSON stream) for conv '{conversation_id}' with input: '{last_user_message_content[:100]}...'")

        async def ndjson_generator():
            full_response = ""
            try:
                async for chunk_dict in agent_executor.astream(
                    {"input": last_user_message_content, "chat_history": chat_history_for_agent}
                ):
                    if "output" in chunk_dict and isinstance(chunk_dict["output"], str):
                        content_piece = chunk_dict["output"]
                        if content_piece:  # Ensure content_piece is not empty
                            full_response += content_piece
                            yield json.dumps({"chunk": content_piece}, ensure_ascii=False) + "\n"
                
                if conversation_id:
                    await storage.add_message(conversation_id, "user", last_user_message_content)
                    await storage.add_message(conversation_id, "assistant", full_response)
                logger.info(f"NDJSON stream complete for conv '{conversation_id}'.")
            except Exception as e:
                logger.error(f"Error during NDJSON stream generation for conv '{conversation_id}': {e}", exc_info=True)
                yield json.dumps({"error": str(e)}, ensure_ascii=False) + "\n"
        
        return Response(stream_with_context(ndjson_generator()), mimetype="application/x-ndjson")

    except Exception as e:
        logger.error(f"Error in /chat-stream POST: {e}", exc_info=True)
        return Response(json.dumps({"error": str(e)}), status=500, mimetype="application/x-ndjson")


@chat_api_bp.route("/chat-sse", methods=["POST"])  # Changed route from /chat/sse to /chat-sse
async def handle_chat_sse_post():
    """
    Handles streaming chat requests (SSE) using the AgentExecutor.
    Accessible at /api/chat-sse
    """
    agent_executor = getattr(current_app, 'agent_executor', None)
    if not agent_executor:
        logger.error("Agent Executor not configured for /chat-sse POST.")
        return Response("data: {\"error\": \"Server agent not available.\"}\n\n", 
                        status=500, 
                        content_type="text/event-stream")

    try:
        data = await request.get_json()
        if not data or "messages" not in data or not data["messages"]:
            return Response("data: {\"error\": \"Invalid request: 'messages' are required.\"}\n\n",
                            status=400,
                            content_type="text/event-stream")

        request_messages = data["messages"]
        conversation_id = data.get("conversation_id")

        last_user_message_content = None
        chat_history_for_agent = []
        if conversation_id:
            stored_messages = await storage.get_messages(conversation_id)
            if stored_messages:
                for msg_data in stored_messages:
                    role, content = msg_data.get("role"), msg_data.get("content")
                    if role == "user": chat_history_for_agent.append(HumanMessage(content=content))
                    elif role == "assistant": chat_history_for_agent.append(AIMessage(content=content))
        
        for i, msg_data in enumerate(request_messages):
            role, content = msg_data.get("role"), msg_data.get("content")
            if role == "user":
                if i == len(request_messages) - 1: last_user_message_content = content
                else: chat_history_for_agent.append(HumanMessage(content=content))
            elif role == "assistant": chat_history_for_agent.append(AIMessage(content=content))

        if not last_user_message_content:
            return Response("data: {\"error\": \"No user input message found.\"}\n\n", status=400, content_type="text/event-stream")

        logger.info(f"Invoking agent (SSE stream) for conv '{conversation_id}' with input: '{last_user_message_content[:100]}...'")

        @stream_with_context
        async def sse_api_generator():
            full_response = ""
            try:
                async for chunk_dict in agent_executor.astream(
                    {"input": last_user_message_content, "chat_history": chat_history_for_agent}
                ):
                    if "output" in chunk_dict and isinstance(chunk_dict["output"], str):
                        content_piece = chunk_dict["output"]
                        if content_piece:  # Ensure content_piece is not empty
                            full_response += content_piece
                            yield f"data: {json.dumps({'chunk': content_piece}, ensure_ascii=False)}\n\n"
                
                if conversation_id:
                    await storage.add_message(conversation_id, "user", last_user_message_content)
                    await storage.add_message(conversation_id, "assistant", full_response)
                logger.info(f"SSE stream complete for conv '{conversation_id}'.")
            except Exception as e:
                logger.error(f"Error during SSE stream generation for conv '{conversation_id}': {e}", exc_info=True)
                yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
        
        return Response(sse_api_generator(), content_type='text/event-stream')

    except Exception as e:
        logger.error(f"Error in /chat-sse POST: {e}", exc_info=True)
        return Response(f"data: {json.dumps({'error': str(e)})}\n\n", status=500, content_type="text/event-stream")
