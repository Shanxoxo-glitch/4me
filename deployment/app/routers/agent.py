from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import httpx
import os
import logging
import json

router = APIRouter()
logger = logging.getLogger(__name__)

class Tool(BaseModel):
    name: str
    description: str
    input_schema: Dict[str, Any]

class AgentTask(BaseModel):
    task: str
    context: Optional[str] = None
    tools: Optional[List[Tool]] = None
    max_iterations: Optional[int] = 10

class AgentResponse(BaseModel):
    result: str
    steps: List[Dict[str, Any]]
    tool_calls: List[Dict[str, Any]]

class ToolCall(BaseModel):
    tool_name: str
    parameters: Dict[str, Any]

class ToolResult(BaseModel):
    result: Any
    error: Optional[str] = None

# Built-in tools
BUILT_IN_TOOLS = [
    Tool(
        name="web_search",
        description="Search the web for information",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"}
            },
            "required": ["query"]
        }
    ),
    Tool(
        name="code_interpreter",
        description="Execute Python code and get results",
        input_schema={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python code to execute"}
            },
            "required": ["code"]
        }
    ),
    Tool(
        name="file_read",
        description="Read contents of a file",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path"}
            },
            "required": ["path"]
        }
    ),
    Tool(
        name="file_write",
        description="Write content to a file",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path"},
                "content": {"type": "string", "description": "Content to write"}
            },
            "required": ["path", "content"]
        }
    )
]

VLLM_URL = os.getenv("VLLM_URL", "http://localhost:8001")

async def call_llm(messages: List[Dict], tools: Optional[List[Tool]] = None) -> Dict:
    """Call the LLM via vLLM"""
    async with httpx.AsyncClient(timeout=300.0) as client:
        payload = {
            "model": os.getenv("MODEL_NAME", "deepseek-ai/DeepSeek-V3"),
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2000,
            "stream": False
        }
        
        if tools:
            payload["tools"] = [tool.dict() for tool in tools]
        
        response = await client.post(f"{VLLM_URL}/v1/chat/completions", json=payload)
        response.raise_for_status()
        return response.json()

async def execute_tool(tool_name: str, parameters: Dict) -> Any:
    """Execute a tool call"""
    try:
        if tool_name == "web_search":
            return {"results": f"Search results for: {parameters.get('query')}"}
        
        elif tool_name == "code_interpreter":
            import sys
            from io import StringIO
            old_stdout = sys.stdout
            sys.stdout = StringIO()
            try:
                exec(parameters.get("code", ""), {})
                output = sys.stdout.getvalue()
                return {"output": output}
            finally:
                sys.stdout = old_stdout
        
        elif tool_name == "file_read":
            try:
                with open(parameters["path"], "r") as f:
                    content = f.read()
                return {"content": content}
            except FileNotFoundError:
                return {"error": "File not found"}
        
        elif tool_name == "file_write":
            try:
                with open(parameters["path"], "w") as f:
                    f.write(parameters["content"])
                return {"success": True}
            except Exception as e:
                return {"error": str(e)}
        
        else:
            return {"error": f"Unknown tool: {tool_name}"}
            
    except Exception as e:
        return {"error": str(e)}

@router.post("/execute", response_model=AgentResponse)
async def execute_agent_task(task: AgentTask):
    """Execute an agentic task using DeepSeek-V3 with tool calling"""
    try:
        max_iterations = task.max_iterations or int(os.getenv("MAX_ITERATIONS", "10"))
        available_tools = task.tools or BUILT_IN_TOOLS
        
        messages = [
            {"role": "system", "content": "You are a helpful AI assistant with access to tools. Use tools when needed to complete tasks."},
            {"role": "user", "content": f"Task: {task.task}"}
        ]
        
        if task.context:
            messages.append({"role": "user", "content": f"Context: {task.context}"})
        
        steps = []
        tool_calls_log = []
        
        for iteration in range(max_iterations):
            llm_response = await call_llm(messages, available_tools)
            content = llm_response["choices"][0]["message"]["content"]
            
            steps.append({
                "iteration": iteration + 1,
                "type": "thought",
                "content": content
            })
            
            messages.append({"role": "assistant", "content": content})
            
            # Simple tool call detection (in production, use proper function calling)
            if "tool:" in content.lower():
                # Extract tool call (simplified)
                try:
                    tool_name = content.split("tool:")[1].split()[0]
                    params = {}
                    if "{" in content and "}" in content:
                        start = content.index("{")
                        end = content.rindex("}") + 1
                        params = json.loads(content[start:end])
                    
                    result = await execute_tool(tool_name, params)
                    tool_calls_log.append({
                        "tool": tool_name,
                        "parameters": params,
                        "result": result
                    })
                    
                    messages.append({
                        "role": "user",
                        "content": f"Tool result: {result}"
                    })
                except Exception as e:
                    logger.error(f"Tool execution error: {e}")
                    break
            else:
                # Task complete
                break
        
        return AgentResponse(
            result=content,
            steps=steps,
            tool_calls=tool_calls_log
        )
        
    except Exception as e:
        logger.error(f"Agent execution error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Agent execution error: {str(e)}")

@router.get("/tools")
async def list_tools():
    """List available tools"""
    return {"tools": BUILT_IN_TOOLS}
