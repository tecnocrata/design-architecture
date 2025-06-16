from langchain.prompts import PromptTemplate
"""
Configuration and constants for the chat application.
"""

# System prompt for the movie assistant
SYSTEM_PROMPT = """You are a helpful movie assistant. Answer ONLY using the information provided in the Context below. If the answer is not in the Context, respond strictly with: 'I don't have information about that in my documents.' Do not use your general knowledge.\n\nContext: {context}\nQuestion: {question}\n"""

SYSTEM_PROMPT_TEMPLATE = PromptTemplate(
    input_variables=["context", "question"],
    template=SYSTEM_PROMPT,
)

# The vector store prompt is only used for retrieval, so it can be simple.
VECTORE_STORE_PROMPT = """Given the following question, retrieve relevant movie information from the database.\n\nQuestion: {question}\n"""

VECTORE_STORE_PROMPT_TEMPLATE = PromptTemplate(
    input_variables=["question"],
    template=VECTORE_STORE_PROMPT,
)