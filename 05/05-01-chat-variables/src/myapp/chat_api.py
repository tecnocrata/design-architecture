from quart import Blueprint, jsonify, redirect, render_template, request, url_for, current_app, Response, stream_with_context
import json
import logging
import asyncio
from langchain.schema import HumanMessage, SystemMessage, AIMessage
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain.chains import RetrievalQA
from langchain_openai import ChatOpenAI
import os
from .config import SYSTEM_PROMPT

# Configure a logger for this blueprint
logger = logging.getLogger(__name__)

chat_api_bp = Blueprint("chat_api", __name__, url_prefix="/api") # , template_folder="templates", static_folder="static"

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

    if not vector_store:
        logger.error("Vector store not initialized.")
        return jsonify({"error": "Vector store not available."}), 500

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

    try:
        logger.debug(f"Sending to LangChain (non-stream) for /api/chat: {messages}")
        
        # Get the last user message
        last_user_message = next((msg["content"] for msg in reversed(messages) if msg["role"] == "user"), None)
        if not last_user_message:
            return jsonify({"error": "No user message found in the conversation."}), 400

        # Create a QA chain with the vector store
        qa_chain = RetrievalQA.from_chain_type(
            llm=chat_model,
            chain_type="stuff",
            retriever=vector_store.as_retriever(search_kwargs={"k": 3})
        )

        # Get relevant context from the vector store
        context_response = await qa_chain.ainvoke({"query": last_user_message})
        if context_response["result"]:
            print(f"Context response (api: {context_response['result']}")
        
        # Convert messages to LangChain message format
        langchain_messages = [SystemMessage(content=SYSTEM_PROMPT)]
        for msg in messages:
            if msg["role"] == "user":
                langchain_messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                langchain_messages.append(AIMessage(content=msg["content"]))
            elif msg["role"] == "system":
                langchain_messages.append(SystemMessage(content=msg["content"]))

        # Add the retrieved context as a system message
        if context_response["result"]:
            langchain_messages.append(SystemMessage(content=f"Here is some relevant information from the movie database: {context_response['result']}"))

        # Get response from LangChain
        response = await chat_model.ainvoke(langchain_messages)
        return jsonify({"reply": response.content})

    except Exception as e:
        logger.error(f"LangChain API call failed for /api/chat: {e}", exc_info=True)
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

    if not vector_store:
        logger.error("Vector store not initialized.")
        error_response = {"error": "Vector store not available."}
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

    @stream_with_context
    async def response_stream_generator():
        try:
            logger.debug(f"Sending to LangChain (stream) for /api/chat-stream: {messages}")
            
            # Get the last user message
            last_user_message = next((msg["content"] for msg in reversed(messages) if msg["role"] == "user"), None)
            if not last_user_message:
                error_response = {"error": "No user message found in the conversation."}
                yield json.dumps(error_response) + "\n"
                return

            # Create a QA chain with the vector store
            qa_chain = RetrievalQA.from_chain_type(
                llm=chat_model,
                chain_type="stuff",
                retriever=vector_store.as_retriever(search_kwargs={"k": 3})
            )

            # Get relevant context from the vector store
            context_response = await qa_chain.ainvoke({"query": last_user_message})
            
            # Convert messages to LangChain message format
            langchain_messages = [SystemMessage(content=SYSTEM_PROMPT)]
            for msg in messages:
                if msg["role"] == "user":
                    langchain_messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    langchain_messages.append(AIMessage(content=msg["content"]))
                elif msg["role"] == "system":
                    langchain_messages.append(SystemMessage(content=msg["content"]))

            # Add the retrieved context as a system message
            if context_response["result"]:
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
                    yield json.dumps(event_dict, ensure_ascii=False) + "\n"

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
