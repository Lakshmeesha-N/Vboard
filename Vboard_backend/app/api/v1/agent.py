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
    """Handle text cleanup and translation requests."""
    try:
        validate_device_id(payload.device_id)
    except InvalidRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        )

    if len(payload.content) > 10000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Content exceeds 10000 characters limit",
        )

    if not payload.content or not payload.content.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Nothing to process",
        )

    parsed_languages = parse_languages(payload.languages)
    languages_str = ",".join(parsed_languages) if parsed_languages else None

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
        "Agent endpoint completed: timing_ms={:.2f}, status_code=200",
        res.elapsed_ms,
    )

    return AgentResponse(
        text=res.text,
        timing_ms=res.elapsed_ms,
    )
