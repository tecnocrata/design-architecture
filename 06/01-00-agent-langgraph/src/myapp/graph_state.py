from typing import List, TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage
import operator

class AgentState(TypedDict):
    """
    Represents the state of our agent.

    Attributes:
        input: The initial user input.
        chat_history: The history of the conversation, an append-only list.
        agent_outcome: The direct response or tool calls from the LLM.
        intermediate_steps: A list of (tool_call, tool_output) tuples, append-only.
                           LangGraph's ToolNode and `add_messages` expect this structure.
        messages: Alias for chat_history, required by LangGraph tools_condition.
    """
    input: str
    chat_history: Annotated[Sequence[BaseMessage], operator.add]
    messages: Annotated[Sequence[BaseMessage], operator.add]  # Alias for chat_history, required by LangGraph tools_condition
    agent_outcome: BaseMessage | None  # LLM's direct response (AIMessage, potentially with tool_calls)
    intermediate_steps: Annotated[list, operator.add] # For tool execution steps
