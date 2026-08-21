from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.agent.graph import ResearchWorkflow
from app.api.schemas import ChatRequest, ChatResponse, HealthResponse
from app.config.settings import get_settings
from app.guardrails.input import InputGuard, InputGuardrailError
from app.guardrails.output import OutputGuard, OutputGuardrailError
from app.llm.deepseek import DeepSeekError, DeepSeekTimeoutError
from app.retrieval.openalex import (
    OpenAlexError,
    OpenAlexTimeoutError,
)

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(status="ok", name=settings.app_name, version=settings.app_version)


def get_research_workflow(request: Request) -> ResearchWorkflow:
    workflow: ResearchWorkflow | None = request.app.state.research_workflow
    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Answer generation is not configured.",
        )
    return workflow


def get_input_guard(request: Request) -> InputGuard:
    return request.app.state.input_guard


def get_output_guard(request: Request) -> OutputGuard:
    return request.app.state.output_guard


@router.post("/chat", response_model=ChatResponse, tags=["research"])
async def chat(
    request: ChatRequest,
    workflow: Annotated[ResearchWorkflow, Depends(get_research_workflow)],
    input_guard: Annotated[InputGuard, Depends(get_input_guard)],
    output_guard: Annotated[OutputGuard, Depends(get_output_guard)],
) -> ChatResponse:
    """Find relevant publications and synthesize an evidence-grounded answer."""
    conversation_id = request.conversation_id or str(uuid4())
    try:
        message = input_guard.validate(request.message)
        (
            answer,
            results,
            show_results,
            authors,
            show_authors,
            context_type,
            suggestions,
        ) = await workflow.run(
            conversation_id=conversation_id,
            message=message,
            filters=request.filters,
        )
        answer = output_guard.validate(
            request=message,
            answer=answer,
            publications=results,
        )
    except InputGuardrailError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    except OutputGuardrailError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The response did not pass Literae's quality checks. Please try again.",
        ) from error
    except OpenAlexTimeoutError as error:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Research search timed out.",
        ) from error
    except OpenAlexError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Research search failed.",
        ) from error
    except DeepSeekTimeoutError as error:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Research request timed out.",
        ) from error
    except DeepSeekError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Research request failed.",
        ) from error

    return ChatResponse(
        conversationId=conversation_id,
        answer=answer,
        results=results,
        showResults=show_results,
        authors=authors,
        showAuthors=show_authors,
        contextType=context_type,
        suggestions=suggestions,
    )
