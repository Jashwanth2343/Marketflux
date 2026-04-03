import asyncio
import os
import json
import time
from dotenv import load_dotenv

# Load ENV
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

import google.generativeai as genai
from react_agent import run_react_agent

# Configure GenAI for the Judge LLM
genai.configure(api_key=os.getenv("GEMINI_API_KEY") or os.getenv("EMERGENT_LLM_KEY"))

# LLM-as-a-Judge evaluation prompt
EVAL_PROMPT = """You are an expert LLM evaluator. 
You must evaluate the response provided by a financial AI agent based on the user's query and the specific formatting rules the agent was supposed to follow.

Formatting Rules to check against:
- Simple factual answer: 1-3 sentences, use bolding for names/numbers.
- Single metric/data questions: MUST use a small, focused Markdown table or bullet points for the data, followed by 1-2 sentences of context. NO plain text only.
- Full analysis: MUST use H3 headers (###), bolding, and large structured tables.

Evaluate the following interaction:
Query: {query}
Agent Response: {response}

Please score the response from 1-5 on the following metrics, and provide a brief justification:
1. Correctness/Helpfulness (1-5): Does the response accurately address the user's intent without hallucinating?
2. Formatting Compliance (1-5): Did it strictly follow the formatting rules above based on the query type?
3. Conciseness (1-5): Did it avoid dumping unrelated data (e.g. dumping a full fundamental table when only asked for one metric)?

Output your evaluation STRICTLY as a JSON object with this shape:
{{
    "correctness_score": int,
    "correctness_justification": "str",
    "formatting_score": int,
    "formatting_justification": "str",
    "conciseness_score": int,
    "conciseness_justification": "str"
}}
"""

async def evaluate_response(query: str, response: str) -> dict:
    """Uses LLM-as-a-judge to evaluate the final response."""
    try:
        model = genai.GenerativeModel('gemini-2.5-flash', generation_config={"response_mime_type": "application/json"})
        prompt = EVAL_PROMPT.format(query=query, response=response)
        result = model.generate_content(prompt)
        return json.loads(result.text)
    except Exception as e:
        print(f"Eval Error: {e}")
        return {
            "correctness_score": 0, "correctness_justification": f"Error: {e}",
            "formatting_score": 0, "formatting_justification": f"Error: {e}",
            "conciseness_score": 0, "conciseness_justification": f"Error: {e}"
        }

async def run_test_case(test_case):
    query = test_case["query"]
    expected_tools_subset = test_case["expected_tools_subset"]
    
    print(f"\nEvaluating Query: '{query}'")
    
    start_time = time.time()
    full_response = ""
    tools_called = set()
    
    try:
        async for event in run_react_agent(query):
            if event.startswith("data: "):
                try:
                    data = json.loads(event[6:])
                    if data["type"] == "thinking" and "step" in data:
                        if data.get("step") == "tools":
                            tools_called.add(data.get("message", "unknown_tool"))
                    elif data["type"] == "tool_call":
                         tools_called.add(data["tool_name"])
                    elif data["type"] == "token":
                        full_response += data["content"]
                except Exception:
                    pass
    except Exception as e:
        full_response += f"\n[Pipeline crashed: {e}]"
        
    latency = time.time() - start_time
    
    print(f"Latency: {latency:.2f}s")
    print(f"Tools Called (Extracted from SSE stream): {tools_called if tools_called else 'Unable to parse from SSE natively, checking manual log not implemented'}")
    
    # 2. Run LLM Judge
    print("Running LLM Evaluation...")
    eval_result = await evaluate_response(query, full_response)
    
    return {
        "query": query,
        "response": full_response,
        "latency": latency,
        "eval_scores": eval_result
    }

# Module-level test cases — importable by autoresearch.py without running main()
TEST_CASES = [
    # Type A: Factual
    {
        "query": "who is the CEO of XOM?",
        "expected_tools_subset": ["get_company_profile"]
    },
    # Type C: Single Metric
    {
        "query": "what's the next earnings date for tesla, what are the consensus expectations",
        "expected_tools_subset": ["get_earnings_history"]
    },
    # Type C: Core Fundamentals
    {
        "query": "what is the P/E ratio and market cap for NVDA?",
        "expected_tools_subset": ["get_fundamentals"]
    },
    # Type E: Full Analysis
    {
        "query": "Give me a full fundamental breakdown of MSFT and tell me if it's a buy.",
        "expected_tools_subset": ["get_fundamentals", "get_analyst_targets"] # expect multiple
    },
    # Type G: General Knowledge (The Fix Verification)
    {
        "query": "What are common factors that drive the stock market?",
        "expected_tools_subset": [] # Should answer from internal knowledge
    },
    # Type M: Market Wide
    {
        "query": "What is driving the market today?",
        "expected_tools_subset": ["get_market_overview"]
    }
]

async def main():
    test_cases = TEST_CASES
    
    results = []
    print("====================================")
    print("STARTING LLM EVALUATION PIPELINE")
    print("====================================")
    
    for case in test_cases:
        res = await run_test_case(case)
        results.append(res)
        
        scores = res['eval_scores']
        print(f" -> Correctness: {scores.get('correctness_score')}/5 - {scores.get('correctness_justification')}")
        print(f" -> Formatting:  {scores.get('formatting_score')}/5 - {scores.get('formatting_justification')}")
        print(f" -> Conciseness: {scores.get('conciseness_score')}/5 - {scores.get('conciseness_justification')}")
        print("------------------------------------")
        
    # Summarize
    avg_correctness = sum(r['eval_scores'].get('correctness_score', 0) for r in results) / len(results)
    avg_formatting = sum(r['eval_scores'].get('formatting_score', 0) for r in results) / len(results)
    avg_conciseness = sum(r['eval_scores'].get('conciseness_score', 0) for r in results) / len(results)
    avg_latency = sum(r['latency'] for r in results) / len(results)
    
    print("\n====================================")
    print("EVALUATION SUMMARY")
    print("====================================")
    print(f"Average Correctness: {avg_correctness:.1f}/5.0")
    print(f"Average Formatting:  {avg_formatting:.1f}/5.0")
    print(f"Average Conciseness: {avg_conciseness:.1f}/5.0")
    print(f"Average Latency:     {avg_latency:.2f}s")
    
    # Save report
    report_path = "eval_report.json"
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Detailed report saved to {report_path}")

if __name__ == "__main__":
    asyncio.run(main())
