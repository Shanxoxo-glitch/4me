from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import httpx
import os
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

class CodeEditRequest(BaseModel):
    code: str
    language: str
    instruction: str
    file_path: Optional[str] = None

class CodeEditResponse(BaseModel):
    edited_code: str
    explanation: str
    changes: List[str]

class CodeReviewRequest(BaseModel):
    code: str
    language: str

class CodeReviewResponse(BaseModel):
    review: str
    issues: List[str]
    suggestions: List[str]

class CodeGenerateRequest(BaseModel):
    description: str
    language: str
    context: Optional[str] = None

class CodeGenerateResponse(BaseModel):
    code: str
    explanation: str

VLLM_URL = os.getenv("VLLM_URL", "http://localhost:8001")

async def call_llm(messages: List[Dict]) -> str:
    """Call the LLM via vLLM"""
    async with httpx.AsyncClient(timeout=300.0) as client:
        response = await client.post(
            f"{VLLM_URL}/v1/chat/completions",
            json={
                "model": os.getenv("MODEL_NAME", "deepseek-ai/DeepSeek-V3"),
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 4000,
                "stream": False
            }
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

@router.post("/edit", response_model=CodeEditResponse)
async def edit_code(request: CodeEditRequest):
    """Edit code based on natural language instructions"""
    try:
        messages = [
            {
                "role": "system",
                "content": f"""You are an expert code editor. Edit the given {request.language} code according to the instruction.
                Return your response in this JSON format:
                {{
                    "edited_code": "the edited code",
                    "explanation": "brief explanation of changes",
                    "changes": ["list of specific changes made"]
                }}"""
            },
            {
                "role": "user",
                "content": f"""Code:
{request.code}

Instruction: {request.instruction}"""
            }
        ]
        
        response = await call_llm(messages)
        
        # Parse JSON response
        import json
        try:
            result = json.loads(response)
            return CodeEditResponse(**result)
        except json.JSONDecodeError:
            # Fallback if not JSON
            return CodeEditResponse(
                edited_code=request.code,
                explanation="Could not parse response as JSON",
                changes=[]
            )
            
    except Exception as e:
        logger.error(f"Code edit error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Code edit error: {str(e)}")

@router.post("/review", response_model=CodeReviewResponse)
async def review_code(request: CodeReviewRequest):
    """Review code for issues and improvements"""
    try:
        messages = [
            {
                "role": "system",
                "content": f"""You are an expert code reviewer. Review the given {request.language} code for:
                - Bugs and errors
                - Security issues
                - Performance issues
                - Code style and best practices
                Return your response in this JSON format:
                {{
                    "review": "overall review summary",
                    "issues": ["list of issues found"],
                    "suggestions": ["list of improvement suggestions"]
                }}"""
            },
            {
                "role": "user",
                "content": f"Code:\n{request.code}"
            }
        ]
        
        response = await call_llm(messages)
        
        import json
        try:
            result = json.loads(response)
            return CodeReviewResponse(**result)
        except json.JSONDecodeError:
            return CodeReviewResponse(
                review=response,
                issues=[],
                suggestions=[]
            )
            
    except Exception as e:
        logger.error(f"Code review error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Code review error: {str(e)}")

@router.post("/generate", response_model=CodeGenerateResponse)
async def generate_code(request: CodeGenerateRequest):
    """Generate code from natural language description"""
    try:
        messages = [
            {
                "role": "system",
                "content": f"""You are an expert programmer. Generate {request.language} code based on the description.
                Return your response in this JSON format:
                {{
                    "code": "the generated code",
                    "explanation": "brief explanation of the code"
                }}"""
            },
            {
                "role": "user",
                "content": f"Description: {request.description}"
            }
        ]
        
        if request.context:
            messages[1]["content"] += f"\n\nContext: {request.context}"
        
        response = await call_llm(messages)
        
        import json
        try:
            result = json.loads(response)
            return CodeGenerateResponse(**result)
        except json.JSONDecodeError:
            return CodeGenerateResponse(
                code=response,
                explanation="Could not parse response as JSON"
            )
            
    except Exception as e:
        logger.error(f"Code generation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Code generation error: {str(e)}")
