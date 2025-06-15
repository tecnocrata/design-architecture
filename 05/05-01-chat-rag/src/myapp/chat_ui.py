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
from .config import SYSTEM_PROMPT

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
@chat_ui_bp.get("/chat/stream")
async def chat_handler():
    """
    Handles chat requests from the client using Server-Sent Events (SSE).
    Receives messages and calls the LangChain API with RAG functionality,
    and streams the response back as SSE events.
    """
    chat_model = getattr(current_app, 'chat_model', None)
    model_name = getattr(current_app, 'model_name', None)

    if not chat_model or not model_name:
        logger.error("LangChain chat model or model name not configured on the current_app.")
        return Response("data: {\"error\": \"Server configuration error.\"}\n\n", 
                       status=500, 
                       content_type="text/event-stream")

    if not vector_store:
        logger.error("Vector store not initialized.")
        return Response("data: {\"error\": \"Vector store not available.\"}\n\n", 
                       status=500, 
                       content_type="text/event-stream")

    if request.method == "GET":
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
            user_message_input = request_messages[-1]["content"]
            user_message_content_to_store = ""

            if isinstance(user_message_input, list):  # Multimodal content
                # Extract text part for simple storage
                user_message_content_to_store = next((part.get("text") for part in user_message_input if part.get("type") == "text"), "")
                # If only image and no text, store a placeholder or handle as per app logic
                if not user_message_content_to_store and image_base64_data_uri and show_multimodal_features:
                    user_message_content_to_store = "[Image received]"
            elif isinstance(user_message_input, str):  # Simple text content
                user_message_content_to_store = user_message_input
            
            if user_message_content_to_store:
                 await storage.add_message(conversation_id, "user", user_message_content_to_store)
            elif show_multimodal_features and image_base64_data_uri: # Case: only image was sent, no text in request_messages[-1]["content"]
                 await storage.add_message(conversation_id, "user", "[Image received]")
            elif not request_messages:
                logger.warning("No messages provided in the request to /chat endpoint for POST.")
                # Potentially return error, or handle as image-only if image_base64_data_uri exists
                if not image_base64_data_uri: # No text and no image
                    return Response("data: {\"error\": \"No messages or image provided in the request.\"}\n\n",
                                  status=400,
                                  content_type="text/event-stream")

        elif show_multimodal_features and image_base64_data_uri: # Only image, no "messages" array
            await storage.add_message(conversation_id, "user", "[Image received]")
        else:
            logger.warning("No messages or image provided in the request to /chat endpoint for POST.")
            return Response("data: {\"error\": \"No messages or image provided in the request.\"}\n\n",
                          status=400,
                          content_type="text/event-stream")

        # For POST request, after storing the user's message,
        # return a confirmation. The actual SSE stream
        # will be handled by the subsequent GET request from EventSource.
        return jsonify({"status": "message_received", "conversation_id": conversation_id})

    @stream_with_context
    async def sse_generator():
        try:
            # 'messages' is populated by the GET request path before this generator is called
            logger.debug(f"SSE Generator: Messages for LangChain: {json.dumps(messages)[:500]}...")

            # Get the last user message's text content for RAG query
            last_user_message_text_content = None
            if messages:
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
                logger.info("No text content found in the last user message for RAG query. Will proceed without RAG context if applicable.")

            # Create a QA chain with the vector store
            qa_chain = RetrievalQA.from_chain_type(
                llm=chat_model,
                chain_type="stuff",
                retriever=vector_store.as_retriever(search_kwargs={"k": 3})
            )
            
            context_response = {"result": None} # Default if no RAG query
            if last_user_message_text_content: # Only query RAG if we have text
                logger.info(f"Performing RAG query with: {last_user_message_text_content}")
                context_response = await qa_chain.ainvoke({"query": last_user_message_text_content})
                if context_response and "result" in context_response and context_response["result"]:
                    logger.info(f"Context response (ui): {context_response['result']}")
            else:
                logger.info("Skipping RAG query as no last user text message content was found.")

            # Convert messages to LangChain message format
            # 'messages' here are from storage.get_messages() in the GET path
            langchain_messages = [SystemMessage(content=SYSTEM_PROMPT)]
            for msg in messages:
                role = msg.get("role")
                content = msg.get("content") # This can be string or list for multimodal

                if role == "user":
                    # HumanMessage content can be a string or a list of content parts (text, image_url)
                    langchain_messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    langchain_messages.append(AIMessage(content=content))
                elif role == "system":
                    langchain_messages.append(SystemMessage(content=content))

            # Add the retrieved context as a system message
            if context_response and "result" in context_response and context_response["result"]:
                langchain_messages.append(SystemMessage(content=f"Here is some relevant information from the movie database: {context_response['result']}"))

            # Stream the response
            full_response = ""
            async for chunk in chat_model.astream(langchain_messages):
                if chunk.content:
                    full_response += chunk.content
                    # Format the response to match the expected SSE format
                    event_dict = {
                        "choices": [{
                            "delta": {"content": chunk.content},
                            "finish_reason": None
                        }]
                    }
                    yield f"data: {json.dumps(event_dict, ensure_ascii=False)}\n\n"

            # Store the complete assistant's reply after streaming is done.
            # 'conversation_id' is in scope from the outer chat_handler (from GET request).
            if full_response: # Ensure there's a response to store
                await storage.add_message(conversation_id, "assistant", full_response)

            # Send a final event to signal completion
            yield f"data: {json.dumps({'event': 'complete'}, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.error(f"LangChain API call failed: {e}", exc_info=True)
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
