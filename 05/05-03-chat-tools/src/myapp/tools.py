# filepath: /workspaces/design-architecture/05/05-03-chat-tools/src/myapp/tools.py
import logging
from langchain_core.tools import tool # Using @tool decorator
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

def get_movie_retriever_tool(retriever: BaseRetriever):
    """
    Creates a movie retriever tool using the @tool decorator.
    The retriever instance is captured from the enclosing scope.
    """
    if not retriever:
        logger.warning("Retriever not provided. Cannot create movie_database_search tool.")
        return None

    @tool
    async def movie_database_search(query: str) -> str:
        """Searches and returns information from the movie database. Use this for any questions about movies, actors, plots, directors, or release dates. Input should be the user's question."""
        logger.info(f"Tool 'movie_database_search' (decorated) invoked with query: '{query}'")
        try:
            docs = await retriever.ainvoke(query)
            if not docs:
                logger.info(f"Tool 'movie_database_search' found no documents for query: '{query}'")
                return ""  # Return empty string if no documents are found

            doc_strings = []
            for doc in docs:
                if isinstance(doc, Document) and hasattr(doc, 'page_content'):
                    doc_strings.append(str(doc.page_content))
                else:
                    doc_strings.append(str(doc)) # Fallback for non-standard doc objects
                    logger.warning(f"Retrieved item was not a standard Document with page_content: {type(doc)}. Converted to string.")
            
            formatted_docs = "\n\n".join(doc_strings)
            logger.info(f"Tool 'movie_database_search' returning {len(docs)} documents. Formatted length: {len(formatted_docs)}")
            return formatted_docs
        except Exception as e:
            logger.error(f"Error in tool 'movie_database_search' during retrieval for query '{query}': {e}", exc_info=True)
            return "" # Return empty string on error

    # The @tool decorator uses the function name (movie_database_search) as the tool's name
    # and its docstring as the description.
    logger.info(f"Movie retriever tool '{movie_database_search.name}' created using @tool decorator.")
    return movie_database_search # Return the decorated tool object

def get_all_tools(vector_store_retriever: BaseRetriever = None):
    """
    Initializes and returns a list of all available tools.
    Currently, only includes the movie retriever tool.
    Args:
        vector_store_retriever: The retriever instance for the vector store.
                                Can be None if the vector store failed to initialize.
    """
    tools = []
    if vector_store_retriever:
        movie_tool = get_movie_retriever_tool(vector_store_retriever) 
        if movie_tool:
            tools.append(movie_tool)
    else:
        logger.warning("Vector store retriever not available. Movie retriever tool will not be created.")
    
    # Future tools can be added here using the @tool decorator on their respective functions
    # e.g.,
    # @tool
    # def another_custom_tool(input_arg: str) -> str:
    #     \"\"\"Description of another custom tool.\"\"\"
    #     # ... logic ...
    #     return "result"
    # tools.append(another_custom_tool)
    
    logger.info(f"Total tools loaded: {len(tools)}")
    return tools
