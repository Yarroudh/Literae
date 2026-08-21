from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent.graph import LangGraphResearchWorkflow, ResearchWorkflow
from app.agent.query_understanding import QueryInterpreter
from app.api.routes import router
from app.common.resilience import ResilientResearchSearcher
from app.config.settings import Settings, get_settings
from app.debugging.laminar import initialize_laminar
from app.guardrails.input import InputGuard
from app.guardrails.output import OutputGuard
from app.history.repository import (
    HistoryRepository,
    NullHistoryRepository,
    PostgresHistoryRepository,
)
from app.llm.deepseek import AnswerGenerator, DeepSeekLLM
from app.retrieval.openalex import OpenAlexClient, ResearchSearcher


def create_app(
    settings: Settings | None = None,
    answer_generator: AnswerGenerator | None = None,
    research_searcher: ResearchSearcher | None = None,
    query_interpreter: QueryInterpreter | None = None,
    research_workflow: ResearchWorkflow | None = None,
    history_repository: HistoryRepository | None = None,
) -> FastAPI:
    app_settings = settings or get_settings()
    laminar_key = (
        app_settings.lmnr_project_api_key.get_secret_value()
        if app_settings.environment != "test" and app_settings.lmnr_project_api_key is not None
        else None
    )
    initialize_laminar(
        project_api_key=laminar_key,
        base_url=app_settings.lmnr_base_url,
        force_http=app_settings.laminar_force_http,
        disable_batch=app_settings.laminar_disable_batch,
    )
    configured_history = history_repository or (
        PostgresHistoryRepository(app_settings.database_url.get_secret_value())
        if app_settings.history_enabled and app_settings.database_url is not None
        else NullHistoryRepository()
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await configured_history.initialize()
        try:
            yield
        finally:
            await configured_history.close()

    application = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        docs_url="/docs" if app_settings.environment != "production" else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    api_key = (
        app_settings.deepseek_api_key.get_secret_value()
        if app_settings.deepseek_api_key is not None
        else ""
    )
    deepseek = (
        DeepSeekLLM(
            api_key=api_key,
            model=app_settings.deepseek_model,
            base_url=app_settings.deepseek_base_url,
            timeout_seconds=app_settings.deepseek_timeout_seconds,
        )
        if api_key
        else None
    )
    configured_answer_generator = answer_generator or deepseek
    configured_query_interpreter = query_interpreter or deepseek
    application.state.answer_generator = configured_answer_generator
    application.state.input_guard = InputGuard()
    application.state.output_guard = OutputGuard()
    application.state.history_repository = configured_history
    openalex_api_key = (
        app_settings.openalex_api_key.get_secret_value()
        if app_settings.openalex_api_key is not None
        else None
    )
    configured_research_searcher = research_searcher or ResilientResearchSearcher(
        OpenAlexClient(
            base_url=app_settings.openalex_base_url,
            api_key=openalex_api_key,
            email=app_settings.openalex_email,
            results_limit=app_settings.openalex_results_limit,
            timeout_seconds=app_settings.openalex_timeout_seconds,
        ),
        cache_ttl_seconds=app_settings.openalex_cache_ttl_seconds,
        retry_attempts=app_settings.service_retry_attempts,
    )
    application.state.research_workflow = research_workflow or (
        LangGraphResearchWorkflow(
            query_interpreter=configured_query_interpreter,
            research_searcher=configured_research_searcher,
            answer_generator=configured_answer_generator,
        )
        if configured_query_interpreter is not None and configured_answer_generator is not None
        else None
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )
    application.include_router(router)
    return application


app = create_app()
