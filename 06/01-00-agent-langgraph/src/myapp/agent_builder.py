import logging
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage, ToolMessage
from langchain_openai import ChatOpenAI

from .graph_state import AgentState
# Assuming get_all_tools returns a list of Langchain tools
# from .tools import get_all_tools will be used in __init__.py
from .config import AGENT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# Helper function to convert stored messages to BaseMessage instances for the graph
def _convert_stored_messages_to_graph_history(stored_messages: list[dict]) -> list[BaseMessage]:
    history = []
    if stored_messages:
        for msg_data in stored_messages:
            role = msg_data.get("role")
            content = msg_data.get("content")
            if role == "user":
                history.append(HumanMessage(content=content))
            elif role == "assistant":
                # If the assistant message had tool calls, they should have been processed
                # and the 'content' here should be the textual part of the response.
                # For simplicity, we assume content is the direct text.
                # If you store structured tool calls/responses, this needs adjustment.
                history.append(AIMessage(content=content))
    return history


def create_agent_graph(chat_model: ChatOpenAI, tools: list):
    """
    Creates and compiles the LangGraph agent.
    """
    logger.info(f"Creating agent graph with {len(tools)} tools.")

    # 1. Define the Agent Node: Responsible for calling the LLM
    async def call_model(state: AgentState):
        logger.debug(f"Agent Node: Calling model. Input: '{state['input']}'")
        messages = [SystemMessage(content=AGENT_SYSTEM_PROMPT)]
        
        # Add existing chat history
        if state.get("chat_history"):
            messages.extend(state["chat_history"])
        
        # Add the current user input
        if state.get("input"):
            messages.append(HumanMessage(content=state["input"]))
        
        llm_with_tools = chat_model.bind_tools(tools)
        
        logger.debug(f"Messages to LLM: {[m.type + ': ' + str(m.content)[:100] for m in messages]}")
        
        try:
            response = await llm_with_tools.ainvoke(messages)
            logger.debug(f"Agent Node: Model response received. Type: {type(response)}, Content: {str(response.content)[:100]}, Tool Calls: {getattr(response, 'tool_calls', None)}")

            updated_history = list(state.get("chat_history", []))
            if state.get("input"):
                updated_history.append(HumanMessage(content=state["input"]))

            # Always append the AIMessage (the LLM's response) to the history
            updated_history.append(response)

            # If the agent wants to use a tool, run the tool and add the result as a ToolMessage
            if getattr(response, "tool_calls", None):
                tool_messages = []
                for tool_call in response.tool_calls:
                    tool_name = tool_call["name"]
                    tool_input = tool_call["args"]
                    tool = next((t for t in tools if t.name == tool_name), None)
                    if tool is None:
                        tool_output = f"Tool '{tool_name}' not found."
                    else:
                        tool_output = await tool.ainvoke(tool_input)
                    tool_message = ToolMessage(
                        content=tool_output,
                        tool_call_id=tool_call["id"]
                    )
                    tool_messages.append(tool_message)
                    updated_history.append(tool_message)
                # Now, call the LLM again with the full sequence
                messages_for_second_call = messages + [response] + tool_messages
                response2 = await llm_with_tools.ainvoke(messages_for_second_call)
                updated_history.append(response2)
                return {
                    "agent_outcome": response2,
                    "input": "",
                    "chat_history": updated_history,
                    "messages": updated_history
                }

            # If no tool calls, just return the response
            return {
                "agent_outcome": response,
                "input": "",
                "chat_history": updated_history,
                "messages": updated_history
            }
        except Exception as e:
            logger.error(f"Error in call_model: {e}", exc_info=True)
            # Return a message indicating error, or re-raise
            error_message = AIMessage(content=f"Sorry, I encountered an error: {e}")
            return {"agent_outcome": error_message, "input": ""}


    # 2. Define the Tool Node
    # ToolNode will append to 'intermediate_steps' with (ToolCall, ToolOutput) tuples
    tool_node = ToolNode(tools)
    logger.info(f"ToolNode created with tools: {[tool.name for tool in tools]}")


    # 3. Construct the Graph
    workflow = StateGraph(AgentState)
    workflow.add_node("agent", call_model)
    workflow.add_node("action", tool_node)

    workflow.set_entry_point("agent")

    # Conditional edge: after 'agent' node, check if tools were called.
    # `tools_condition` checks `state['agent_outcome'].tool_calls`.
    # If tool_calls exist, it routes to 'action'. Otherwise, to END.
    workflow.add_conditional_edges(
        "agent",
        tools_condition, # Prebuilt condition
        {
            "tools": "action", # If agent_outcome has tool_calls
            END: END          # Otherwise (no tool_calls, direct answer)
        },
    )
    
    # After 'action' (tool execution), route back to 'agent' to process tool results.
    # The ToolNode appends tool outputs to 'intermediate_steps'.
    # The 'agent' node needs to be designed to incorporate these `intermediate_steps`
    # by converting them into ToolMessage objects for the next LLM call.
    # Langchain's `AIMessage(tool_calls=...)` and `ToolMessage(content=..., tool_call_id=...)`
    # are the standard way to represent this.
    # The `call_model` function needs to be aware of `intermediate_steps` if this loop is active.
    # For now, we'll let the agent decide what to do with the history and new input.
    # A more robust agent would explicitly format ToolMessages from intermediate_steps.
    workflow.add_edge("action", "agent")

    try:
        compiled_graph = workflow.compile()
        # To enable history with checkpoints, you'd pass a checkpointer here:
        # from langgraph.checkpoint.aiosqlite import AsyncSqliteSaver
        # memory = AsyncSqliteSaver.from_conn_string(":memory:")
        # compiled_graph = workflow.compile(checkpointer=memory)
        logger.info("LangGraph agent compiled successfully.")
        return compiled_graph
    except Exception as e:
        logger.error(f"Error compiling graph: {e}", exc_info=True)
        raise
