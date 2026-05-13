"""Smoke test for LLM integration.

Verifies that the configured model correctly handles both free-text (call_llm)
and structured JSON (call_llm_json) requests without leaking thinking tags
or crashing on format expectations.

Run this after any model swap or API provider change.
"""

import json
import time
from src.llm import call_llm, call_llm_json
from src.config import MODEL_NAME


def test_free_text():
    print(f"Testing call_llm (free text) with {MODEL_NAME}...")
    start = time.time()
    try:
        response = call_llm(
            system_prompt="You are a helpful assistant.",
            user_prompt="Say the exact phrase 'Hello World' and nothing else.",
            temperature=0.0
        )
        elapsed = time.time() - start
        
        if "<think>" in response or "</think>" in response:
            print("❌ FAILED: Response leaked <think> tags.")
            return False
            
        if "Hello World" not in response:
            print(f"❌ FAILED: Unexpected response content.\nGot: {repr(response)}")
            return False
            
        print(f"✅ PASSED ({elapsed:.2f}s)\n  Response: {repr(response)}")
        return True
    except Exception as e:
        print(f"❌ FAILED: Exception raised: {e}")
        return False


def test_json():
    print(f"\nTesting call_llm_json (structured output) with {MODEL_NAME}...")
    start = time.time()
    try:
        response_str = call_llm_json(
            system_prompt="You are a JSON generator. Return ONLY valid JSON.",
            user_prompt='Return a single JSON object with a key "status" set to the string "ok".',
            temperature=0.0
        )
        elapsed = time.time() - start
        
        if "<think>" in response_str or "</think>" in response_str:
            print("❌ FAILED: Response leaked <think> tags.")
            return False
            
        try:
            parsed = json.loads(response_str)
            if parsed.get("status") != "ok":
                print(f"❌ FAILED: Valid JSON, but unexpected content: {parsed}")
                return False
            print(f"✅ PASSED ({elapsed:.2f}s)\n  Parsed: {parsed}")
            return True
        except json.JSONDecodeError as e:
            print(f"❌ FAILED: Could not parse JSON. Error: {e}\nRaw output: {repr(response_str)}")
            return False
            
    except Exception as e:
        print(f"❌ FAILED: Exception raised: {e}")
        return False


if __name__ == "__main__":
    print(f"=== Running LLM Smoke Tests ===")
    print(f"Model: {MODEL_NAME}")
    print("=" * 31)
    
    t1 = test_free_text()
    t2 = test_json()
    
    if t1 and t2:
        print("\n🎉 All smoke tests passed. LLM integration is healthy.")
        exit(0)
    else:
        print("\n💀 Smoke tests failed. Do not run the pipeline.")
        exit(1)
