import os
from typing import Annotated, Literal
from langchain_core.messages import HumanMessage, BaseMessage
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict
from tools import all_tools

print("🤖 Starting agent initialization...")

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    next_agent: Literal["Supervisor", "SoilCropAdvisor", "MarketAnalyst", "FinancialAdvisor", "FinalAnswerAgent", "end"]

llm = ChatGroq(temperature=0, model_name="llama3-8b-8192", api_key=os.getenv("GROQ_API_KEY"))
llm_with_tools = llm.bind_tools(all_tools)
tool_node = ToolNode(all_tools)
print("✅ Groq LLM, tools, and ToolNode initialized.")

# --- Agent Definitions ---

def supervisor_agent(state: AgentState):
    """The Supervisor routes the query to a specialist agent or directly to the FinalAnswerAgent."""
    messages = state['messages']
    user_input = messages[-1].content
    
    prompt = f"""You are the supervisor of a team of expert AI agents for Indian agriculture.
Based on the user's query, determine which specialist agent is best suited. If no specialist tool is needed (e.g., for a general question or greeting), route to the FinalAnswerAgent.

Your available specialist agents are:
- SoilCropAdvisor: For soil health, crop recommendations, farming techniques, weather, and disaster alerts.
- MarketAnalyst: For current market prices of crops in specific locations (mandis).
- FinancialAdvisor: For government schemes, subsidies, loans, and financial planning.
- FinalAnswerAgent: For synthesizing a final response or answering general knowledge questions.

User Query: "{user_input}"

Analyze the query.
- If it clearly requires a tool (price, weather, scheme info), respond with the specialist agent's name.
- If it's a general question ("what is the best crop in odisha?"), a greeting, or a follow-up, respond with "FinalAnswerAgent".

Respond with ONLY the agent name.
"""
    response = llm.invoke(prompt)
    next_agent_name = response.content.strip()
    
    valid_agents = ["SoilCropAdvisor", "MarketAnalyst", "FinancialAdvisor", "FinalAnswerAgent"]
    if next_agent_name not in valid_agents:
        next_agent_name = "FinalAnswerAgent" # Default to final answer agent
        
    print(f"🎯 Supervisor routing to: {next_agent_name}")
    return {"next_agent": next_agent_name}

def specialist_agent_node(state: AgentState):
    """A generic node for all specialist agents. It runs the LLM with tools."""
    print(f"🔄 Specialist agent is processing the query to find tools...")
    response = llm_with_tools.invoke(state['messages'])
    return {"messages": [response]}

def final_answer_agent(state: AgentState):
    """This agent synthesizes the final, user-facing answer based on the full conversation history."""
    print("✍️ Synthesizing final answer...")
    
    # Create a prompt that includes the full conversation history
    synthesis_prompt = f"""You are a helpful and professional agricultural assistant for farmers in India.
Your goal is to provide a clear, comprehensive, and well-rounded answer based on the entire conversation history.
The history may include the user's original question and data retrieved by specialist tools.

Synthesize all the information into a single, high-quality response.
- Address the user's original query directly.
- If data was found (like prices or weather), incorporate it naturally into your response.
- If no specific data was found or needed, provide a helpful, general answer.
- Do not mention agents, tools, or the internal process. Speak directly to the farmer.

Here is the conversation history:
{state['messages']}

Now, please provide the final, complete answer for the user.
"""
    response = llm.invoke(synthesis_prompt)
    return {"messages": [response]}

# --- Graph Definition ---

def router(state: AgentState):
    """Routes to tools if called, otherwise routes to the FinalAnswerAgent to synthesize a response."""
    last_message = state["messages"][-1]
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        print("🔧 Routing to tools...")
        return "tools"
    
    print("✅ Tools not required or already used. Routing to FinalAnswerAgent.")
    return "FinalAnswerAgent"

def supervisor_router(state: AgentState):
    """Directs flow from the supervisor to the correct next node."""
    return state.get("next_agent", "FinalAnswerAgent")

# Create the graph
workflow = StateGraph(AgentState)

workflow.add_node("Supervisor", supervisor_agent)
workflow.add_node("SoilCropAdvisor", specialist_agent_node)
workflow.add_node("MarketAnalyst", specialist_agent_node)
workflow.add_node("FinancialAdvisor", specialist_agent_node)
workflow.add_node("FinalAnswerAgent", final_answer_agent)
workflow.add_node("tools", tool_node)

# Define the workflow edges
workflow.set_entry_point("Supervisor")

workflow.add_conditional_edges("Supervisor", supervisor_router, {
    "SoilCropAdvisor": "SoilCropAdvisor",
    "MarketAnalyst": "MarketAnalyst",
    "FinancialAdvisor": "FinancialAdvisor",
    "FinalAnswerAgent": "FinalAnswerAgent"
})

workflow.add_conditional_edges("SoilCropAdvisor", router, {"tools": "tools", "FinalAnswerAgent": "FinalAnswerAgent"})
workflow.add_conditional_edges("MarketAnalyst", router, {"tools": "tools", "FinalAnswerAgent": "FinalAnswerAgent"})
workflow.add_conditional_edges("FinancialAdvisor", router, {"tools": "tools", "FinalAnswerAgent": "FinalAnswerAgent"})

# After tools are used, go back to the FinalAnswerAgent to synthesize the response
workflow.add_edge("tools", "FinalAnswerAgent")
workflow.add_edge("FinalAnswerAgent", END)

agentic_workflow = workflow.compile()
print("🎉 New agentic workflow with FinalAnswerAgent compiled successfully!")