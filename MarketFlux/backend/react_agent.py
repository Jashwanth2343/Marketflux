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
_REACT_PROMPT_TEMPLATE = """\
You are MarketFlux AI, a world-class financial research assistant.
Your goal is to provide deep, analytical, and visually stunning responses.

TODAY'S DATE: {{TODAY}}
You MUST use this date as your reference point. All "current" and "recent" data refers to {{TODAY}}. Do NOT reference events, prices, or data from previous years unless explicitly discussing historical context.

===== COMMAND: EXECUTION OVER DESCRIPTION =====

- LIVE DATA IS ALWAYS AVAILABLE: You have access to a real-time market snapshot (Indices, VIX, Fear & Greed) which is injected into your context. Use THESE exact numbers if the user asks any macro or market questions.
- DATA IS MANDATORY: Never describe what a section *would* contain. You MUST populate every section with actual numbers from the live tools.
- FRESH ANALYSIS ONLY: Always perform a fresh, full analysis using tools for every request.
- NO META-DESCRIPTION: Just show the data.
- CURRENT DATA ONLY: When discussing current market conditions, ONLY use data from your tools. Do NOT fill in numbers from your training data — if a tool doesn't return a value, say "data unavailable" instead of guessing.

===== AUTONOMOUS AGENT — THINK AND ACT FREELY =====

You are an AUTONOMOUS financial analyst. You decide what tools to call, in what order, and how many.
- If the user asks about a stock, proactively fetch snapshot, fundamentals, news, AND analyst targets — don't wait to be told.
- For comparisons, fetch data for ALL mentioned companies before analyzing.
- For deep questions, call SEC financials, earnings transcripts, and macro data.
- For market/macro questions, call macro context, sector performance, and FRED data.
- You may call tools in parallel when multiple stocks need the same data.
- Think step by step. Use your reasoning to determine what data you need next.
- NEVER refuse to answer. If a tool fails, try a different approach or use the web search fallback.

===== PREMIUM DESIGN PRINCIPLES =====

1. VISUAL EXCELLENCE: Use rich Markdown (##, ###, bold). Format like a Goldman Sachs research note.
2. TABLES ARE MANDATORY: Every numerical data point MUST be in a table. Use `|`.
3. ANALYTICAL PROSE: Every section must start with a 1-sentence expert takeaway.
4. MACRO QUESTIONS: For questions like "why is the market risk-off today?" first output a small Markdown table titled **Drivers** (2–8 rows, columns: Driver | Impact) that lists the main causes, then follow with your normal sections. Every macro/market response MUST use the live index/VIX/Fear & Greed data provided in the snapshot. When the user asks about sectors ("which sectors are most impacted"), call get_sector_performance and present the sector performance table with leading/lagging analysis.

===== RESPONSE LENGTH RULES — NON-NEGOTIABLE =====

You are a precision instrument, not a research report generator. Match your response length exactly to what was asked. More words do not mean better answers.

company_info queries (CEO, headquarters, founded date, employee count, website, leadership):
- Maximum: 2 sentences OR one small table (3 rows max)
- Only include the specific person/place/date asked for
- NEVER add financial metrics, P/E, revenue, or margins
- NEVER add the investment disclaimer
- Correct: "Tim Cook has been Apple's CEO since 2011."
- Wrong: anything with a fundamentals table attached

price_lookup queries (current price, single metric):
- State the number in the first sentence always
- One sentence of context maximum
- No tables unless the user asked to compare tickers
- NEVER add the investment disclaimer

The investment disclaimer ending with "Always do your own research before investing" is ONLY for:
deep_analysis, stock_analysis, comparison queries.

It is NEVER appropriate for: company_info, price_lookup, factual, general_chat, macro_overview queries.
Attaching an investment disclaimer to "who is the CEO" is like a restaurant adding a health warning to a glass of water. It signals the system is not smart enough to know context.

End every report with: "This analysis is based on available data. Always do your own research before investing." (ONLY IF APPLICABLE PER RULES ABOVE)
"""

def _build_react_system_prompt():
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%A, %B %d, %Y")
    return _REACT_PROMPT_TEMPLATE.replace("{{TODAY}}", today)

REACT_SYSTEM_PROMPT = _build_react_system_prompt()

def get_react_model(model_id: str = "gemini-2.5-flash", system_instruction: str = None):
    if system_instruction is None:
        system_instruction = _build_react_system_prompt()
    from ai_service import configure_gemini
    configure_gemini()
        
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }

    # Define the tools — comprehensive set for autonomous operation
    tools = [
        agent_tools.get_stock_snapshot,
        agent_tools.get_fundamentals,
        agent_tools.get_analyst_targets,
        agent_tools.get_news,
        agent_tools.get_technical_indicators,
        agent_tools.get_insider_transactions,
        agent_tools.get_macro_context,
        agent_tools.get_market_overview_tool,
        agent_tools.get_sector_performance,
        agent_tools.web_search,
        agent_tools.web_search_news,
        agent_tools.tavily_search,
        agent_tools.get_company_profile_tool,
        agent_tools.get_sec_financials,
        agent_tools.get_fred_macro,
        agent_tools.get_earnings_transcript,
    ]

    # Enable thinking/reasoning for complex queries (requires newer SDK)
    generation_config = None
    if model_id and 'pro' in model_id:
        try:
            generation_config = genai.types.GenerationConfig(
                thinking_config=genai.types.ThinkingConfig(
                    thinking_budget=8192
                )
            )
        except (AttributeError, TypeError) as e:
            logger.info(f"Thinking mode not available in this SDK version ({e}), proceeding without it")
            generation_config = None

    model_kwargs = {
        "model_name": model_id,
        "system_instruction": system_instruction,
        "safety_settings": safety_settings,
        "tools": tools,
    }
    if generation_config:
        model_kwargs["generation_config"] = generation_config

    model = genai.GenerativeModel(**model_kwargs)
    return model

def _sse_event(event_type: str, data: dict) -> str:
    """Format a Server-Sent Event line."""
    return f"data: {json.dumps({'type': event_type, **data})}\n\n"

def _thinking_event(step: str, message: str) -> str:
    return _sse_event("thinking", {"step": step, "message": message})

def _token_event(content: str) -> str:
    return _sse_event("token", {"content": content})

def _done_event(**extra) -> str:
    return _sse_event("done", extra)

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
    "get_sector_performance": agent_tools.get_sector_performance,
    "web_search": agent_tools.web_search,
    "web_search_news": agent_tools.web_search_news,
    "tavily_search": agent_tools.tavily_search,
    "get_company_profile": agent_tools.get_company_profile_tool,
    "get_company_profile_tool": agent_tools.get_company_profile_tool,
    "get_sec_financials": agent_tools.get_sec_financials,
    "get_fred_macro": agent_tools.get_fred_macro,
    "get_earnings_transcript": agent_tools.get_earnings_transcript,
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
    Supports PARALLEL function calls (multiple tools in one response).
    Streams reasoning logs (SSE) to the frontend.
    """
    # 1. Classify intent to get model routing and prompt additions
    from agent_router import classify_intent, INTENT_PROMPTS
    from ai_service import select_model_id, GEMINI_FLASH
    
    yield _thinking_event("intent", "🤔 Planning strategy and model selection...")
    intent_data = await classify_intent(message)
    query_type = intent_data.get("query_type", "stock_analysis")
    
    model_id = select_model_id(message, intent=query_type, user_id=user_id)
    
    # 2. Build personalized system prompt
    current_system_prompt = _build_react_system_prompt()
    if query_type in INTENT_PROMPTS:
        current_system_prompt += f"\n\n{INTENT_PROMPTS[query_type]}"
        
    model = get_react_model(model_id=model_id, system_instruction=current_system_prompt)
    
    # 3. Determine tool call ceiling — generous for comparison/deep queries
    if max_tool_calls is None:
        if query_type in ("company_info", "price_lookup", "factual"):
            max_tool_calls = 2
        elif query_type in ("stock_analysis", "technical_analysis", "news_query", "insider_activity"):
            max_tool_calls = 6
        elif query_type in ("comparison", "deep_analysis", "portfolio_review"):
            max_tool_calls = 15
        else:
            max_tool_calls = 10
    
    logger.info(f"ReAct Agent initialized: query_type={query_type}, model={model_id}, max_tool_calls={max_tool_calls}")
    
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
    all_tool_results = {}  # Accumulate for fallback when LLM fails
    
    def _extract_function_calls(resp):
        """Extract ALL function_call parts from a response (supports parallel calls)."""
        calls = []
        if resp.parts:
            for part in resp.parts:
                if hasattr(part, 'function_call') and part.function_call and part.function_call.name:
                    calls.append(part.function_call)
        return calls

    def _has_text_response(resp):
        """Check if the response contains any text content (not just function calls)."""
        if resp.parts:
            for part in resp.parts:
                if hasattr(part, 'text') and part.text and part.text.strip():
                    return True
        return False

    def _get_text_from_response(resp):
        """Extract all text content from response parts."""
        texts = []
        if resp.parts:
            for part in resp.parts:
                if hasattr(part, 'text') and part.text:
                    texts.append(part.text)
        return "".join(texts)
    
    # We loop over the chat interaction. If model returns function_call(s), we execute and loop again.
    try:
        # First turn
        response = await asyncio.to_thread(chat.send_message, user_prompt)
        
        iteration = 0
        max_iterations = max_tool_calls + 5  # safety net to prevent infinite loops
        
        while tool_call_count < max_tool_calls and iteration < max_iterations:
            iteration += 1
            
            # Extract ALL function calls from the response (parallel tool calling)
            function_calls = _extract_function_calls(response)
            
            if not function_calls:
                # No more function calls — model is done (or returned text)
                break
            
            # Process all function calls in this response (parallel execution)
            function_responses = []
            
            for function_call in function_calls:
                if tool_call_count >= max_tool_calls:
                    logger.info(f"Hit tool call limit ({max_tool_calls}), skipping remaining calls")
                    break
                
                tool_name = function_call.name
                args = dict(function_call.args)
                
                # Prevent duplicate tool calls
                tool_signature = f"{tool_name}:{str(sorted(args.items()))}"
                if tool_signature in called_tools:
                    logger.info(f"Skipping duplicate tool call: {tool_signature}")
                    # Still need to send a response for this call
                    function_responses.append({
                        "function_response": {
                            "name": tool_name,
                            "response": {"note": "Already fetched this data."}
                        }
                    })
                    continue
                called_tools.add(tool_signature)
                
                tool_call_count += 1
                logger.info(f"Agent Loop {tool_call_count}/{max_tool_calls}: Calling {tool_name} with {args}")
                
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
                        
                # Robust Serialization
                tool_result = _sanitize_tool_result(tool_result)
                if not isinstance(tool_result, dict):
                    tool_result = {"result": tool_result}
                
                # Accumulate for fallback
                tool_key = tool_name
                if args.get("ticker"):
                    tool_key = f"{tool_name}:{args['ticker']}"
                elif args.get("query") and tool_name in ("web_search", "web_search_news", "tavily_search"):
                    tool_key = f"{tool_name}:{str(args.get('query', ''))[:20]}"
                all_tool_results[tool_key] = tool_result
                
                logger.info(f"Tool result for {tool_name} (size: {len(str(tool_result))})")
                
                function_responses.append({
                    "function_response": {
                        "name": tool_name,
                        "response": tool_result
                    }
                })
            
            if not function_responses:
                break
            
            # Send ALL function responses back to model in one message
            response = await asyncio.to_thread(
                chat.send_message,
                {
                    "role": "function",
                    "parts": function_responses
                }
            )
            # Loop continues — model may request more tools or return text
                    
        # If we hit the loop limit and model still wants tools, force final response
        if tool_call_count >= max_tool_calls:
            remaining_calls = _extract_function_calls(response)
            if remaining_calls:
                logger.warning(f"Agent hit {max_tool_calls} tool call limit. Forcing final response.")
                yield _thinking_event("generate", "Assembling final response from collected data...")
                response = await asyncio.to_thread(
                    chat.send_message, 
                    "You have reached the maximum tool call limit. STOP calling tools immediately. "
                    "PROVIDE YOUR FINAL COMPREHENSIVE ANALYSIS NOW using ALL the data you have collected. "
                    "Format it with proper markdown, tables, and structured sections."
                )
            
        # Extract the final text response
        final_text = None
        
        # Attempt 1: Get text directly from response
        try:
            final_text = response.text
        except (ValueError, AttributeError):
            pass
        
        # If no text, try extracting from parts manually
        if not final_text and _has_text_response(response):
            final_text = _get_text_from_response(response)
        
        # Attempt 2: Ask model to summarize what it has
        if not final_text:
            logger.warning("Model did not provide text. Requesting explicit summary...")
            try:
                response = await asyncio.to_thread(
                    chat.send_message,
                    "You MUST provide your analysis NOW. Do NOT call any more tools. "
                    "Write a complete, well-formatted markdown response analyzing all the data you've gathered. "
                    "Include tables for numerical comparisons."
                )
                try:
                    final_text = response.text
                except (ValueError, AttributeError):
                    if _has_text_response(response):
                        final_text = _get_text_from_response(response)
            except Exception as e:
                logger.error(f"Summary request failed: {e}")
        
        # Attempt 3: Use a fresh Flash model with all tool data as context (no function calling)
        if not final_text and all_tool_results:
            logger.warning("Primary model failed to produce text. Trying Flash model with tool context...")
            yield _thinking_event("generate", "Formatting analysis...")
            try:
                from agent_router import _format_tool_context
                from ai_service import configure_gemini
                configure_gemini()
                
                tool_context = _format_tool_context(all_tool_results)
                symbols = intent_data.get("symbols", [])
                
                fallback_prompt = (
                    f"You are MarketFlux AI. The user asked: \"{message}\"\n\n"
                    f"Here is ALL the live data collected from our tools:\n\n"
                    f"--- TOOL RESULTS ---\n{tool_context[:8000]}\n--- END TOOL RESULTS ---\n\n"
                    f"Provide a comprehensive, well-formatted analysis. "
                    f"Use markdown headers (###), tables for all numerical data, and professional finance language. "
                )
                
                if len(symbols) >= 2:
                    fallback_prompt += (
                        f"This is a COMPARISON query for {', '.join(symbols)}. "
                        f"Create a side-by-side comparison table with Price, Change%, Market Cap, P/E, "
                        f"Revenue Growth, Margins, and Analyst Rating. Follow with comparative analysis."
                    )
                
                fallback_prompt += "\nEnd with: 'This analysis is based on available data. Always do your own research before investing.'"
                
                safety_settings = {
                    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                }
                
                fallback_model = genai.GenerativeModel(
                    GEMINI_FLASH,
                    system_instruction=current_system_prompt,
                    safety_settings=safety_settings,
                    # No tools — forces text response
                )
                
                fallback_response = await asyncio.to_thread(
                    fallback_model.generate_content, fallback_prompt
                )
                final_text = fallback_response.text
                logger.info("Flash fallback model produced text successfully.")
            except Exception as fb_err:
                logger.error(f"Flash fallback failed: {fb_err}")
        
        # Attempt 4: Last resort — build structured response from raw tool data
        if not final_text:
            logger.error("All LLM attempts failed. Building response from raw tool data.")
            try:
                from agent_router import _format_tool_context
                ctx = _format_tool_context(all_tool_results)[:4000] if all_tool_results else ""
                if ctx:
                    final_text = (
                        f"### Market Data Summary\n\n{ctx}\n\n"
                        "*AI formatting was temporarily unavailable. Data above is from live sources — please try again for a fuller analysis.*"
                    )
                else:
                    final_text = "I've gathered the market data but am having trouble assembling the final report. Please try again in a moment."
            except Exception:
                final_text = "I've gathered the market data but am having trouble assembling the final report. Please try again in a moment."

        yield _thinking_event("generate", "Writing analysis...")
        yield _token_event("") # Initial marker for router
        
        # Stream the final text
        chunk_size = 50
        for i in range(0, len(final_text), chunk_size):
            chunk = final_text[i:i+chunk_size]
            yield _token_event(chunk)
            full_text_response += chunk
            await asyncio.sleep(0.005)
            
        # Pass chart_tickers to frontend for comparison charts
        done_payload = {}
        symbols = intent_data.get("symbols", [])
        if len(symbols) >= 2:
            done_payload["chart_tickers"] = symbols[:5]
        yield _done_event(**done_payload)
        
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
