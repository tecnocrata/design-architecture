import json
import logging
import uuid  # For generating conversation IDs if needed
from quart import (
    Blueprint,
    render_template,
    request,
    Response,
    current_app,
    stream_with_context,
    jsonify,
)
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, ToolMessage
from .storage import ConversationStorage  # Assuming storage is accessible
from .agent_builder import _convert_stored_messages_to_graph_history  # Helper for history

# Define the Blueprint for the chat UI and API
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

@chat_ui_bp.post("/conversations")
async def create_conversation():
    """Create a new conversation and return its ID."""
    try:
        storage: ConversationStorage = getattr(current_app, 'conversation_storage', None)
        if not storage:
            logger.error("Conversation storage not found in current_app.")
            return jsonify({"error": "Conversation storage not available"}), 500
        conversation_id = await storage.create_conversation()
        return jsonify({"conversation_id": conversation_id})
    except Exception as e:
        logger.error(f"Error creating conversation: {e}")
        return jsonify({"error": "Failed to create conversation"}), 500

@chat_ui_bp.get("/conversations/<conversation_id>")
async def get_conversation(conversation_id: str):
    """Get a conversation by ID."""
    try:
        storage: ConversationStorage = getattr(current_app, 'conversation_storage', None)
        if not storage:
            logger.error("Conversation storage not found in current_app.")
            return jsonify({"error": "Conversation storage not available"}), 500
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

@chat_ui_bp.route("/chat/stream", methods=["POST"])
async def handle_chat_post():
    """Handles chat messages, streams responses using LangGraph."""
    data = await request.get_json()
    # Support both legacy and new payloads
    user_message_content = None
    conversation_id = None
    # Newer payload (from chat.html):
    if data.get("messages") and isinstance(data["messages"], list):
        # Find the last user message
        for msg in reversed(data["messages"]):
            if msg.get("role") == "user":
                user_message_content = msg.get("content")
                break
        # Get conversation_id from sessionState if present
        session_state = data.get("sessionState")
        if session_state and isinstance(session_state, dict):
            conversation_id = session_state.get("conversation_id")
        # Fallback: try top-level conversation_id
        if not conversation_id:
            conversation_id = data.get("conversation_id")
    else:
        # Legacy/simple payload
        user_message_content = data.get("message")
        conversation_id = data.get("conversation_id")

    # logger = logging.getLogger("quart.app")
    compiled_graph = getattr(current_app, 'compiled_graph', None)
    storage: ConversationStorage = getattr(current_app, 'conversation_storage', None)

    if not compiled_graph:
        logger.error("Compiled graph not found in current_app.")
        return Response(json.dumps({"error": "Chat agent not available"}), status=500, content_type="application/json")
    if not storage:
        logger.error("Conversation storage not found in current_app.")
        return Response(json.dumps({"error": "Conversation storage not available"}), status=500, content_type="application/json")
    if not user_message_content:
        return Response(json.dumps({"error": "Empty message"}), status=400, content_type="application/json")

    if not conversation_id:
        conversation_id = await storage.create_conversation()
        logger.info(f"New conversation started with ID: {conversation_id}")
    else:
        logger.info(f"Continuing conversation with ID: {conversation_id}")

    # Retrieve and convert chat history for the graph
    stored_messages_dict = await storage.get_messages(conversation_id)  # Returns List[Dict]
    chat_history_for_graph = _convert_stored_messages_to_graph_history(stored_messages_dict)

    # Patch: LangGraph tool routing expects a 'messages' key in the state
    graph_input = {
        "input": user_message_content,
        "chat_history": chat_history_for_graph,
        "messages": chat_history_for_graph,  # Ensure compatibility with tools_condition
        "intermediate_steps": []
    }

    full_assistant_response_content = ""
    try:
        # Add current user message to storage before streaming, so history is up-to-date
        await storage.add_message(conversation_id, "user", user_message_content)
        
        logger.info(f"Streaming request to LangGraph for conversation '{conversation_id}'. Input: '{user_message_content[:50]}...'")
        
        # Run the compiled graph and collect the response
        async for event in compiled_graph.astream(graph_input):
            logger.debug(f"LangGraph Stream Event for {conversation_id}: {event}")
            if "agent" in event:
                agent_outcome = event["agent"].get("agent_outcome")
                if isinstance(agent_outcome, AIMessage):
                    if agent_outcome.content:
                        chunk_content = agent_outcome.content
                        if isinstance(chunk_content, str):
                            full_assistant_response_content += chunk_content
        # After the graph finishes (all tools run, final agent response), save the full assistant response.
        if full_assistant_response_content:
            await storage.add_message(conversation_id, "assistant", full_assistant_response_content)
            logger.info(f"Saved assistant response to conversation {conversation_id}: '{full_assistant_response_content[:100]}...'")
        # Return the response as JSON
        return Response(json.dumps({
            "choices": [{"delta": {"content": full_assistant_response_content}, "finish_reason": None}],
            "conversation_id": conversation_id,
            "event": "complete"
        }, ensure_ascii=False), content_type="application/json")
    except Exception as e:
        logger.error(f"Error during LangGraph streaming for conversation {conversation_id}: {e}", exc_info=True)
        error_event = {
            "error": str(e),
            "conversation_id": conversation_id
        }
        return Response(json.dumps(error_event, ensure_ascii=False), content_type="application/json", status=500)
    finally:
        logger.info(f"POST /chat/stream completed for conversation {conversation_id}.")

@chat_ui_bp.get("/chat/stream")
async def handle_chat_get_stream():
    """Handles GET requests for SSE communication."""
    logger.info("Handling GET request for chat stream.------")
    conversation_id = request.args.get("conversation_id")
    # logger = logging.getLogger("quart.app")
    compiled_graph = getattr(current_app, 'compiled_graph', None)
    storage: ConversationStorage = getattr(current_app, 'conversation_storage', None)

    if not compiled_graph:
        logger.error("Compiled graph not found in current_app.")
        return Response("data: {\"error\": \"Chat agent not available\"}\n\n", status=500, content_type="text/event-stream")
    if not storage:
        logger.error("Conversation storage not found in current_app.")
        return Response("data: {\"error\": \"Conversation storage not available\"}\n\n", status=500, content_type="text/event-stream")
    if not conversation_id:
        return Response("data: {\"error\": \"Invalid request: 'conversation_id' is required\"}\n\n", status=400, content_type="text/event-stream")

    # Retrieve and convert chat history for the graph
    stored_messages_dict = await storage.get_messages(conversation_id)  # Returns List[Dict]
    chat_history_for_graph = _convert_stored_messages_to_graph_history(stored_messages_dict)

    @stream_with_context
    async def sse_generator():
        try:
            graph_input = {
                "input": "",  # No new input for GET requests
                "chat_history": chat_history_for_graph,
                "messages": chat_history_for_graph,  # Ensure compatibility with tools_condition
                "intermediate_steps": []
            }

            logger.info(f"Streaming history for conversation '{conversation_id}' via SSE.")

            async for event in compiled_graph.astream(graph_input):
                logger.debug(f"LangGraph Stream Event for {conversation_id}: {event}")
                if "agent" in event:
                    agent_outcome = event["agent"].get("agent_outcome")
                    if isinstance(agent_outcome, AIMessage):
                        # Only yield if this is a final answer (no tool calls)
                        if agent_outcome.content and not getattr(agent_outcome, "tool_calls", None):
                            chunk_content = agent_outcome.content
                            if isinstance(chunk_content, str):
                                sse_event_data = {
                                    "choices": [{"delta": {"content": chunk_content}, "finish_reason": None}],
                                    "conversation_id": conversation_id,
                                }
                                yield f"data: {json.dumps(sse_event_data, ensure_ascii=False)}\n\n"

            # If no content was yielded, send a placeholder event to avoid silent connection close
            if not chat_history_for_graph or all(
                not (isinstance(msg, AIMessage) and msg.content) for msg in chat_history_for_graph
            ):
                yield f"data: {json.dumps({'error': 'No assistant response generated.'}, ensure_ascii=False)}\n\n"

            # Send a completion event
            completion_event = {
                "event": "complete", 
                "conversation_id": conversation_id,
            }
            yield f"data: {json.dumps(completion_event, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.error(f"Error during LangGraph streaming for conversation {conversation_id}: {e}", exc_info=True)
            error_event = {
                "error": str(e),
                "conversation_id": conversation_id
            }
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
        finally:
            logger.info(f"SSE stream completed for conversation {conversation_id}.")

    return Response(sse_generator(), content_type="text/event-stream")
