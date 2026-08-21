from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from typing import Any

try:
    from lmnr import Instruments, Laminar
except ImportError:  # Allows tests and deployments to run without the optional debugger.
    Instruments = None  # type: ignore[assignment]
    Laminar = None  # type: ignore[assignment,misc]


_enabled = False


def initialize_laminar(
    *,
    project_api_key: str | None,
    base_url: str | None = None,
    force_http: bool = True,
    disable_batch: bool = True,
) -> bool:
    """Enable backend tracing when a Laminar key and SDK are available."""
    global _enabled
    if not project_api_key or Laminar is None or Instruments is None:
        _enabled = False
        return False

    options: dict[str, object] = {
        "project_api_key": project_api_key,
        "instruments": {Instruments.OPENAI},
        "force_http": force_http,
        "disable_batch": disable_batch,
    }
    if base_url:
        options["base_url"] = base_url.rstrip("/")
    Laminar.initialize(**options)
    _enabled = True
    return True


@contextmanager
def trace_span(
    name: str,
    *,
    input_data: object | None = None,
    session_id: str | None = None,
) -> Iterator[None]:
    if not _enabled or Laminar is None:
        yield
        return
    with Laminar.start_as_current_span(
        name=name,
        input=input_data,
        session_id=session_id,
    ):
        yield


def traced_node(
    name: str,
    node: Callable[[dict[str, Any]], Awaitable[dict[str, object]] | dict[str, object]],
) -> Callable[[dict[str, Any]], Awaitable[dict[str, object]]]:
    """Wrap a LangGraph node without leaking tracing concerns into node logic."""

    async def wrapped(state: dict[str, Any]) -> dict[str, object]:
        with trace_span(name, input_data=_state_summary(state)):
            result = node(state)
            if isinstance(result, Awaitable):
                result = await result
            if _enabled and Laminar is not None:
                Laminar.set_span_output(_result_summary(result))
            return result

    wrapped.__name__ = name
    return wrapped


def _state_summary(state: dict[str, Any]) -> dict[str, object]:
    plan = state.get("search_plan")
    return {
        "message": state.get("message", ""),
        "route": state.get("route"),
        "intent": getattr(plan, "intent", None),
        "context_type": state.get("context_type"),
        "paper_count": len(state.get("results", [])),
        "author_count": len(state.get("authors", [])),
    }


def _result_summary(result: dict[str, object]) -> dict[str, object]:
    return {
        "route": result.get("route"),
        "action": result.get("action"),
        "context_type": result.get("context_type"),
        "paper_count": len(result.get("results", [])),
        "author_count": len(result.get("authors", [])),
        "has_answer": bool(result.get("answer")),
        "suggestion_count": len(result.get("suggestions", [])),
    }
