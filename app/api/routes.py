from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.agent.graph import ResearchWorkflow
from app.api.schemas import (
    ChatRequest,
    ChatResponse,
    ConversationHistory,
    ConversationSummary,
    HealthResponse,
)
from app.config.settings import get_settings
from app.guardrails.input import InputGuard, InputGuardrailError
from app.guardrails.output import OutputGuard, OutputGuardrailError
from app.history.repository import HistoryRepository
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


def get_history_repository(request: Request) -> HistoryRepository:
    return request.app.state.history_repository


@router.post("/chat", response_model=ChatResponse, tags=["research"])
async def chat(
    request: ChatRequest,
    workflow: Annotated[ResearchWorkflow, Depends(get_research_workflow)],
    input_guard: Annotated[InputGuard, Depends(get_input_guard)],
    output_guard: Annotated[OutputGuard, Depends(get_output_guard)],
    history: Annotated[HistoryRepository, Depends(get_history_repository)],
) -> ChatResponse:
    """Find relevant publications and synthesize an evidence-grounded answer."""
    conversation_id = request.conversation_id or str(uuid4())
    try:
        message = input_guard.validate(request.message)
        prior_context = await history.latest_context(conversation_id)
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
            context=prior_context,
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

    response = ChatResponse(
        conversationId=conversation_id,
        answer=answer,
        results=results,
        showResults=show_results,
        authors=authors,
        showAuthors=show_authors,
        contextType=context_type,
        suggestions=suggestions,
    )
    await history.save_turn(
        conversation_id,
        message,
        response.model_dump(mode="json", by_alias=True, exclude={"conversation_id"}),
    )
    return response


@router.get("/conversations", response_model=list[ConversationSummary], tags=["history"])
async def list_conversations(
    history: Annotated[HistoryRepository, Depends(get_history_repository)],
) -> list[ConversationSummary]:
    return [ConversationSummary.model_validate(item) for item in await history.list_conversations()]


@router.get(
    "/conversations/{conversation_id}", response_model=ConversationHistory, tags=["history"]
)
async def get_conversation(
    conversation_id: str,
    history: Annotated[HistoryRepository, Depends(get_history_repository)],
) -> ConversationHistory:
    conversation = await history.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
    return ConversationHistory.model_validate(conversation)


@router.delete("/conversations/{conversation_id}", status_code=204, tags=["history"])
async def delete_conversation(
    conversation_id: str,
    history: Annotated[HistoryRepository, Depends(get_history_repository)],
) -> None:
    if not await history.delete_conversation(conversation_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
