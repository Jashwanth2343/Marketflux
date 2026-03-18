import asyncio
import os
import sys

# Add current dir to path
sys.path.append(os.getcwd())

async def verify_fix():
    print("--- VERIFYING REACT AGENT FIX ---")
    
    from react_agent import run_react_agent
    
    # Test 1: Market Overview query (should use get_market_overview_tool)
    message = "What is driving the market today?"
    print(f"\nTesting Query: {message}")
    
    events_received = []
    try:
        async for event in run_react_agent(message, max_tool_calls=2):
            events_received.append(event)
            # Print simplified event info
            if "thinking" in event:
                print(f"[THINKING] {event}")
            elif "token" in event:
                # print(".", end="", flush=True)
                pass
            elif "done" in event:
                print("\n[DONE]")
                
        # Check if we got tokens (actual response)
        has_tokens = any("token" in e for e in events_received)
        if has_tokens:
            print("SUCCESS: Received text tokens from ReAct agent.")
        else:
            print("FAILURE: No text tokens received.")
            
    except Exception as e:
        print(f"CRASH: ReAct Agent raised an exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(verify_fix())
