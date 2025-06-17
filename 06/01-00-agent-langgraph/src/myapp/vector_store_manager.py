import logging
import os
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

logger = logging.getLogger(__name__)

def initialize_vector_store(embeddings_api_key: str):
    """
    Initializes the vector store with movie data using TextLoader and Chroma.
    Constructs an absolute path to 'movies.txt' relative to this file.
    """
    try:
        # Determine the absolute path to 'movies.txt'
        # This assumes 'movies.txt' is in the same directory as this manager.
        current_dir = os.path.dirname(os.path.abspath(__file__))
        movies_file_path = os.path.join(current_dir, "movies.txt")

        if not os.path.exists(movies_file_path):
            logger.error(f"Movies file not found at: {movies_file_path}")
            # Attempt a fallback path assuming execution from project root, common in some setups
            # This is a bit of a guess, ideally paths are configured or consistently relative.
            fallback_movies_file_path = os.path.join(os.getcwd(), "src", "myapp", "movies.txt")
            if os.path.exists(fallback_movies_file_path):
                movies_file_path = fallback_movies_file_path
                logger.info(f"Using fallback movies file path: {movies_file_path}")
            else:
                logger.error(f"Fallback movies file also not found at: {fallback_movies_file_path}")
                # Check if the file exists at the original hardcoded path from chat_ui.py as a last resort
                original_hardcoded_path = "src/myapp/movies.txt" # Relative to project root
                if os.path.exists(original_hardcoded_path):
                     movies_file_path = original_hardcoded_path
                     logger.info(f"Using original hardcoded path for movies file: {movies_file_path}")
                else:
                    logger.error(f"Original hardcoded movies file also not found at: {original_hardcoded_path}")
                    return None


        logger.info(f"Loading documents from: {movies_file_path}")
        loader = TextLoader(movies_file_path, encoding="utf-8")
        documents = loader.load()

        if not documents:
            logger.error(f"No documents loaded from {movies_file_path}. Check the file content and permissions.")
            return None

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        docs = text_splitter.split_documents(documents)

        if not docs:
            logger.error(f"No documents to process after text splitting from {movies_file_path}.")
            return None

        logger.info(f"Initializing embeddings with model 'text-embedding-3-small'.")
        embeddings = OpenAIEmbeddings(
            openai_api_key=embeddings_api_key, # Use the passed API key
            model="text-embedding-3-small"
        )

        logger.info(f"Creating Chroma vector store from {len(docs)} documents.")
        vector_store = Chroma.from_documents(docs, embeddings)
        logger.info("Chroma vector store initialized successfully.")
        return vector_store
    except Exception as e:
        logger.error(f"Error initializing vector store: {e}", exc_info=True)
        return None
