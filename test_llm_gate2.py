import asyncio
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
import os
from agent_service import llm, generate_procedure_route

class GateDecision(BaseModel):
    use_procedure: bool
    reason: str
    confidence: float

gate_prompt = "You are an expert procedure-gating agent. Decide if this procedure is useful: 'Click button'. Task: 'Click button'."

async def test():
    try:
        print("Invoking LLM...")
        res = await llm.with_structured_output(GateDecision).ainvoke(gate_prompt)
        print("Success:", res)
    except Exception as e:
        print("Error:", repr(e))

asyncio.run(test())
