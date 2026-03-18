import os
import json
import logging
import asyncio
from typing import AsyncGenerator, Optional
from datetime import datetime, timezone
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# Import our God-Tier tools
import agent_tools

logger = logging.getLogger(__name__)

# System Prompt explicitly crafted for ReAct agent
# Updated for PREMIUM formatting, analytical intelligence, and FRESH data enforcement.
# Base system prompt for ReAct agent
REACT_SYSTEM_PROMPT = """You are MarketFlux AI, a world-class financial research assistant.
Your goal is to provide deep, analytical, and visually stunning responses.

═══════════════════════════════════════
COMMAND: EXECUTION OVER DESCRIPTION
═══════════════════════════════════════

- LIVE DATA IS ALWAYS AVAILABLE: You have access to a real-time market snapshot (Indices, VIX, Fear & Greed) which is injected into your context. Use THESE exact numbers if the user asks any macro or market questions.
- DATA IS MANDATORY: Never describe what a section *would* contain. You MUST populate every section with actual numbers from the live tools.
- FRESH ANALYSIS ONLY: Always perform a fresh, full analysis using tools for every request.
- NO META-DESCRIPTION: Just show the data.

═══════════════════════════════════════
PREMIUM DESIGN PRINCIPLES
═══════════════════════════════════════

1. VISUAL EXCELLENCE: Use rich Markdown (##, ###, bold). Format like a Goldman Sachs research note.
2. TABLES ARE MANDATORY: Every numerical data point MUST be in a table. Use `|`. 
3. ANALYTICAL PROSE: Every section must start with a 1-sentence expert takeaway. 
4. MACRO QUESTIONS: Every macro/market response MUST use the live index/VIX/Fear & Greed data provided in the snapshot.

═══════════════════════════════════════
RESPONSE LENGTH RULES — NON-NEGOTIABLE:
═══════════════════════════════════════

You are a precision instrument, not a research report generator. Match your response length exactly to what was asked. More words do not mean better answers.

company_info queries (CEO, headquarters, founded date, employee count, website, leadership):
→ Maximum: 2 sentences OR one small table (3 rows max)
→ Only include the specific person/place/date asked for
→ NEVER add financial metrics, P/E, revenue, or margins
→ NEVER add the investment disclaimer
→ Correct: "Tim Cook has been Apple's CEO since 2011."
→ Wrong: anything with a fundamentals table attached

price_lookup queries (current price, single metric):
→ State the number in the first sentence always
→ One sentence of context maximum
→ No tables unless the user asked to compare tickers
→ NEVER add the investment disclaimer

The investment disclaimer ending with "Always do your own research before investing" is ONLY for:
deep_analysis, stock_analysis, comparison queries.

It is NEVER appropriate for: company_info, price_lookup, factual, general_chat, macro_overview queries.
Attaching an investment disclaimer to "who is the CEO" is like a restaurant adding a health warning to a glass of water. It signals the system is not smart enough to know context.

End every report with: "This analysis is based on available data. Always do your own research before investing." (ONLY IF APPLICABLE PER RULES ABOVE)
"""

def get_react_model(model_id: str = "models/gemini-flash-latest", system_instruction: str = REACT_SYSTEM_PROMPT):
    # Safely get key
    from ai_service import configure_gemini
    configure_gemini()
        
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }

    # Define the tools exactly as imported
    tools = [
        agent_tools.get_stock_snapshot,
        agent_tools.get_fundamentals,
        agent_tools.get_analyst_targets,
        agent_tools.get_news,
        agent_tools.get_technical_indicators,
        agent_tools.get_insider_transactions,
        agent_tools.get_macro_context,
        agent_tools.get_market_overview_tool,
        agent_tools.web_search,
        agent_tools.web_search_news,
        agent_tools.tavily_search,
        agent_tools.get_company_profile_tool
    ]

    model = genai.GenerativeModel(
        model_id,
        system_instruction=system_instruction,
        safety_settings=safety_settings,
        tools=tools
    )
    return model

def _sse_event(event_type: str, data: dict) -> str:
    """Format a Server-Sent Event line."""
    return f"data: {json.dumps({'type': event_type, **data})}\n\n"

def _thinking_event(step: str, message: str) -> str:
    return _sse_event("thinking", {"step": step, "message": message})

def _token_event(content: str) -> str:
    return _sse_event("token", {"content": content})

def _done_event() -> str:
    return _sse_event("done", {})

def _sanitize_tool_result(data):
    """Recursively converts non-serializable objects (like Decimal or custom classes) to strings/primitives."""
    from decimal import Decimal
    
    if isinstance(data, dict):
        return {str(k): _sanitize_tool_result(v) for k, v in data.items()}
    elif isinstance(data, (list, tuple)):
        return [_sanitize_tool_result(i) for i in data]
    elif isinstance(data, (int, float, str, bool)) or data is None:
        return data
    elif isinstance(data, Decimal):
        return float(data)
    else:
        try:
            return str(data)
        except Exception:
            return "[Unserializable Object]"

_TOOL_MAPPING = {
    "get_stock_snapshot": agent_tools.get_stock_snapshot,
    "get_fundamentals": agent_tools.get_fundamentals,
    "get_analyst_targets": agent_tools.get_analyst_targets,
    "get_news": agent_tools.get_news,
    "get_technical_indicators": agent_tools.get_technical_indicators,
    "get_insider_transactions": agent_tools.get_insider_transactions,
    "get_macro_context": agent_tools.get_macro_context,
    "get_market_overview": agent_tools.get_market_overview_tool,
    "get_market_overview_tool": agent_tools.get_market_overview_tool,
    "web_search": agent_tools.web_search,
    "web_search_news": agent_tools.web_search_news,
    "tavily_search": agent_tools.tavily_search,
    "get_company_profile": agent_tools.get_company_profile_tool,
    "get_company_profile_tool": agent_tools.get_company_profile_tool,
}

async def run_react_agent(
    message: str,
    history: Optional[list] = None,
    db=None,
    user_id: str = "",
    session_id: str = "",
    context_str: str = "",
    max_tool_calls: Optional[int] = None
) -> AsyncGenerator[str, None]:
    """
    Executes the true ReAct loop (Agentic) using Gemini Function Calling.
    Max 5 tool iterations. Streams reasoning logs (SSE) to the frontend.
    """
    # 1. Classify intent to get model routing and prompt additions
    from agent_router import classify_intent, INTENT_PROMPTS
    from ai_service import select_model_id
    
    yield _thinking_event("intent", "🤔 Planning strategy and model selection...")
    intent_data = await classify_intent(message)
    query_type = intent_data.get("query_type", "stock_analysis")
    
    model_id = select_model_id(message, intent=query_type, user_id=user_id)
    
    # 2. Build personalized system prompt
    current_system_prompt = REACT_SYSTEM_PROMPT
    if query_type in INTENT_PROMPTS:
        current_system_prompt += f"\n\n{INTENT_PROMPTS[query_type]}"
        
    model = get_react_model(model_id=model_id, system_instruction=current_system_prompt)
    
    # 3. Determine tool call ceiling
    if max_tool_calls is None:
        if query_type in ("company_info", "price_lookup", "factual"):
            max_tool_calls = 1
        elif query_type in ("stock_analysis", "technical_analysis", "news_query", "insider_activity"):
            max_tool_calls = 5
        else:
            max_tool_calls = 10  # Increased for complex discovery queries
    
    logger.info(f"ReAct Agent initialized: query_type={query_type}, max_tool_calls={max_tool_calls}")
    
    # Initialize chat history
    gemini_history = []
    if history:
        for h in history[-10:]:
            msg = h.get("message", "")
            resp = h.get("response", "")
            if isinstance(msg, str) and isinstance(resp, str) and len(msg) > 10 and len(resp) > 10:
                gemini_history.append({"role": "user", "parts": [msg]})
                gemini_history.append({"role": "model", "parts": [resp]})
            
    chat = model.start_chat(history=gemini_history)
    
    # Send the first message
    yield _thinking_event("intent", "Planning research strategy...")
    
    user_prompt = message
    if context_str:
        user_prompt = f"Page Context: {context_str}\n\nUser Question: {message}"

    tool_call_count = 0
    full_text_response = ""
    called_tools = set()
    
    # We loop over the chat interaction. If model returns a function_call, we execute and loop again.
    try:
        # First turn
        response = await asyncio.to_thread(chat.send_message, user_prompt)
        
        while tool_call_count < max_tool_calls:
            # Check if there are function calls
            if response.parts:
                part = response.parts[0]
                if part.function_call:
                    function_call = part.function_call
                    tool_name = function_call.name
                    args = dict(function_call.args)
                    
                    # Fix: Prevent duplicate tool calls
                    tool_signature = f"{tool_name}:{str(sorted(args.items()))}"
                    if tool_signature in called_tools:
                        logger.info(f"Skipping duplicate tool call: {tool_signature}")
                        break
                    called_tools.add(tool_signature)

                    tool_call_count += 1
                    logger.info(f"Agent Loop {tool_call_count}: Calling {tool_name} with {args}")
                    
                    # Yield friendly thinking event to frontend
                    display_msg = f"Executing {tool_name.replace('_', ' ')}..."
                    if "ticker" in args:
                        display_msg = f"Fetching {args['ticker']} data ({tool_name.replace('_', ' ')})..."
                    elif "query" in args:
                        display_msg = f"Searching web for '{args['query']}'..."
                        
                    yield _thinking_event("tools", display_msg)
                    
                    # Execute python function
                    func = _TOOL_MAPPING.get(tool_name)
                    if not func:
                        # Fallback: check if the model used the function name instead of mapping key
                        func = getattr(agent_tools, tool_name, None)

                    if not func:
                        tool_result = {"error": f"Tool {tool_name} not found."}
                    else:
                        try:
                            if asyncio.iscoroutinefunction(func):
                                tool_result = await asyncio.wait_for(func(**args), timeout=30.0)
                            else:
                                tool_result = await asyncio.wait_for(
                                    asyncio.to_thread(func, **args), timeout=30.0
                                )
                        except asyncio.TimeoutError:
                            logger.warning(f"Tool {tool_name} timed out")
                            tool_result = {"error": f"{tool_name} timed out. Proceeding with available data."}
                        except Exception as e:
                            logger.error(f"Tool execution failed: {e}")
                            tool_result = {"error": f"Tool {tool_name} failed: {str(e)}"}
                            
                    # Robust Serialization Fix:
                    tool_result = _sanitize_tool_result(tool_result)
                    if not isinstance(tool_result, dict):
                        tool_result = {"result": tool_result}
                    
                    logger.info(f"Sending tool result for {tool_name} (size: {len(str(tool_result))})")

                    # Send result back to model
                    response = await asyncio.to_thread(
                        chat.send_message,
                        {
                            "role": "function",
                            "parts": [
                                {
                                    "function_response": {
                                        "name": tool_name,
                                        "response": tool_result
                                    }
                                }
                            ]
                        }
                    )
                    continue
                else:
                    # Model provided text response, we are done
                    break
            else:
                break
                    
        # If we hit the loop limit, force it to summarize what it has
        if tool_call_count >= max_tool_calls:
            if response.parts and response.parts[0].function_call:
                logger.warning(f"Agent hit {max_tool_calls} tool call limit. Forcing final response.")
                yield _thinking_event("generate", "Assembling final response from collected data...")
                response = await asyncio.to_thread(
                    chat.send_message, 
                    "You have reached the maximum tool call limit. STOP calling tools and PROVIDE YOUR FINAL SUMMARY NOW using the data you have collected."
                )
            
        # We now have the final text response, stream it back as tokens for UI
        try:
            final_text = response.text
        except ValueError:
            logger.error("Model refused to provide text. Doing one final attempt.")
            try:
                response = await asyncio.to_thread(chat.send_message, "Summarize your findings in 3 sentences.")
                final_text = response.text
            except Exception:
                final_text = "I've gathered the market data but am having trouble assembling the final report. Please check back in a moment or try a more specific question."

        yield _thinking_event("generate", "Writing analysis...")
        yield _token_event("") # Initial marker for router
        
        # Simulating token stream
        chunk_size = 50
        for i in range(0, len(final_text), chunk_size):
            chunk = final_text[i:i+chunk_size]
            yield _token_event(chunk)
            full_text_response += chunk
            await asyncio.sleep(0.005)
            
        yield _done_event()
        
        # Save to database
        
        # Save to database
        if db is not None:
            try:
                await db.chat_messages.insert_one({
                    "user_id": user_id,
                    "session_id": session_id,
                    "message": message,
                    "response": full_text_response,
                    "query_type": "react_agent",
                    "created_at": datetime.now(timezone.utc)
                })
            except Exception as e:
                logger.error(f"DB save error: {e}")
                
    except Exception as e:
        logger.critical(
            f"ReAct Agent crashed | message='{message[:100]}' | "
            f"tool_calls_completed={tool_call_count} | error={type(e).__name__}: {str(e)}",
            exc_info=True
        )
        raise e
