from fastapi import APIRouter, HTTPException, status
from loguru import logger

from app.core.exceptions import InvalidRequestError
from app.core.validators import parse_languages, validate_device_id
from app.schemas.agent import AgentRequest, AgentResponse
from app.services import agent_service

router = APIRouter()
agent_router = router


@router.post("/agent", response_model=AgentResponse)
async def handle_agent(payload: AgentRequest) -> AgentResponse:
    """Handle agent and cleanup requests."""
    try:
        validate_device_id(payload.device_id)
    except InvalidRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    if len(payload.content) > 10000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Content exceeds 10000 characters limit",
        )

    parsed_languages = parse_languages(payload.languages)
    languages_str = ",".join(parsed_languages) if parsed_languages else None

    if agent_service.route(payload.content) == "agent":
        res = await agent_service.agent_branch(
            payload.content, languages=languages_str
        )
    else:
        res = await agent_service.cleanup_branch(
            payload.content, languages=languages_str
        )

    if not res.text or not res.text.strip():
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM produced empty text",
        )

    # Privacy requirement: log numerical metrics only, never user content or output
    logger.info(
        "Agent endpoint completed: rounds={}, timing_ms={:.2f}, "
        "used_search={}, status_code=200",
        res.rounds,
        res.elapsed_ms,
        res.used_search,
    )

    return AgentResponse(
        text=res.text,
        used_search=res.used_search,
        rounds=res.rounds,
        note=res.note,
        timing_ms=res.elapsed_ms,
    )
