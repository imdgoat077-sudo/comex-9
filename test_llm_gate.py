import asyncio
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
import os

MODEL_NAME = os.environ.get("OPENAI_MODEL_NAME", "gpt-4o")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "not-needed-if-local")

llm = ChatOpenAI(
    model=MODEL_NAME,
    base_url=OPENAI_BASE_URL,
    api_key=OPENAI_API_KEY,
    temperature=0.0
)

class GateDecision(BaseModel):
    use_procedure: bool
    reason: str
    confidence: float

gate_prompt = "You are an expert. Say yes to use procedure, reason='good', confidence=0.9."

def main():
    try:
        res = llm.with_structured_output(GateDecision).invoke(gate_prompt)
        print("Success:", res)
    except Exception as e:
        print("Error:", e)

main()
