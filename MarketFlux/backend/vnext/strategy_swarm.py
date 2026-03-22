import asyncio
import json
import uuid
import datetime
import re
from typing import Dict, Any, List
from .model_router import StrategyLLMRouter

def strip_thinking_tokens(text: str) -> str:
    # Remove <think>...</think> blocks (reasoning models leak these)
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    # Also strip any orphaned closing tags
    text = re.sub(r'</think>', '', text)
    text = re.sub(r'<think>', '', text)
    return text.strip()

def extract_tickers(prompt: str) -> list[str]:
    # Match uppercase 1-5 letter words that look like tickers
    return re.findall(r'\b[A-Z]{1,5}\b', prompt)

AGENT_PERSONAS = {
    "bull": {
        "name": "Bull Case Agent",
        "system": "You are an optimistic analyst. Find the strongest possible upside case for this trade. What tailwinds, catalysts, and data points support a long position? Be specific and cite numbers. 3 bullet points max."
    },
    "bear": {
        "name": "Bear Case Agent", 
        "system": "You are a skeptical analyst. Find the strongest possible downside case and risks. What could go wrong? What are the red flags in the data? Be specific. 3 bullet points max."
    },
    "value": {
        "name": "Value Agent",
        "system": "You are a value-focused analyst in the style of Benjamin Graham. Is this asset cheap or expensive relative to fundamentals? What is a rough intrinsic value estimate? 3 bullet points max."
    },
    "momentum": {
        "name": "Momentum Agent",
        "system": "You are a technical/tape analyst. What does price action, volume, and market structure say? Is momentum confirming or denying the thesis? 3 bullet points max."
    },
    "risk": {
        "name": "Risk Officer",
        "system": "You are the risk officer. Given the bull and bear cases, what is the appropriate position size for a $100k portfolio? Provide: max position size as % of portfolio, suggested stop-loss level, and one condition that invalidates the entire thesis immediately."
    }
}

SYNTHESIS_SYSTEM = """You are the Portfolio Manager. You have received analysis from 5 specialists who sometimes disagree. Your job is to resolve the debate and produce a concrete trade plan. Output exactly this structure:

VERDICT: [LONG / SHORT / PASS]
CONVICTION: [1-10]
ENTRY: [price range or condition]
TARGET: [price target with timeframe]
STOP: [stop-loss level]
SIZE: [% of portfolio]
THESIS: [2 sentences max — why this trade exists]
INVALIDATION: [one specific condition that kills the trade immediately]
DISSENT: [which agent disagreed most and why it matters]"""

async def run_swarm_agent(router: StrategyLLMRouter, agent_key: str, agent_config: Dict[str, str], prompt: str, session_id: str, yield_callback = None) -> Dict[str, Any]:
    messages = [
        {"role": "system", "content": agent_config["system"]},
        {"role": "user", "content": prompt}
    ]
    # Use fast models for speed on individual agents
    result = await router.complete(
        messages=messages, 
        reasoning=False, 
        session_id=session_id,
        request_purpose=f"swarm_{agent_key}"
    )
    
    result = strip_thinking_tokens(result)
    
    agent_output = {
        "agent": agent_key,
        "name": agent_config["name"],
        "content": result
    }
    
    if yield_callback:
        await yield_callback({
            "type": "agent", 
            "agent": {
                "agent_id": agent_key,
                "name": agent_config["name"],
                "summary": result,
                "confidence": 85,
                "trade_expression": "Analysis done"
            }
        })
        
    return agent_output

async def run_swarm(prompt: str, regime_context: Dict[str, Any], tickers: List[str], user_id: str, yield_callback=None) -> Dict[str, Any]:
    router = StrategyLLMRouter()
    session_id = str(uuid.uuid4())
    
    tickers_found = extract_tickers(prompt)
    ticker_context = f"Tickers being analyzed: {', '.join(tickers_found) if tickers_found else 'general market'}"
    
    # Enrich prompt with regime context
    enriched_prompt = f"""
USER PROMPT: {prompt}
TICKERS MENTIONED: {ticker_context}
CURRENT MACRO REGIME: {json.dumps(regime_context)}

Execute your analysis based on the above information.
"""

    if yield_callback:
        await yield_callback({"type": "status", "message": "Initiating parallel swarm..."})

    # Run the 5 agents in parallel
    tasks = []
    for key, config in AGENT_PERSONAS.items():
        tasks.append(run_swarm_agent(router, key, config, enriched_prompt, session_id, yield_callback))
        
    agents_results = await asyncio.gather(*tasks)
    
    # Synthesize
    if yield_callback:
        await yield_callback({"type": "status", "message": "Synthesizing agent outputs..."})
        
    synthesis_context = "SWARM OUTPUTS:\n\n"
    for r in agents_results:
        synthesis_context += f"--- {r['name']} ---\n{r['content']}\n\n"
        
    synthesis_messages = [
        {"role": "system", "content": SYNTHESIS_SYSTEM},
        {"role": "user", "content": f"USER PROMPT: {prompt}\n\n{synthesis_context}"}
    ]
    
    final_strategy = await router.complete(
        messages=synthesis_messages,
        reasoning=True,
        session_id=session_id,
        request_purpose="swarm_synthesis"
    )
    
    final_strategy = strip_thinking_tokens(final_strategy)
    
    if yield_callback:
        words = final_strategy.split(' ')
        for word in words:
            await asyncio.sleep(0.02)
            await yield_callback({"type": "token", "content": word + ' '})
            
    return {
        "session_id": session_id,
        "prompt": prompt,
        "agents_output": agents_results,
        "final_strategy": final_strategy,
        "regime_used": regime_context,
        "is_paper": True,
        "execution_status": "pending_approval",
        "created_by": user_id
    }
