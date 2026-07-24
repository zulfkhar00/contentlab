from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_project_scope
from app.db.session import get_db
from app.domain.errors import DomainError, ProjectNotFound
from app.domain.scope import ProjectScope
from app.intelligence.factory import get_intelligence_provider
from app.schemas.revision import ApplyRevisionRequest
from app.schemas.variant import (
    BriefPatchRequest,
    ExecutionObservationRequest,
    ObservationResponse,
    ReviseBriefRequest,
    SubmitUrlRequest,
    VariantResponse,
    VideoResponse,
)
from app.services.variant_service import VariantService
from app.repositories.video_repo import VideoRepository

router = APIRouter(prefix="/api/variants", tags=["variants"])

@router.post("/{variant_id}/apply-revision", response_model=VariantResponse)
async def apply_revision(
    variant_id: UUID,
    body: ApplyRevisionRequest,
    scope: ProjectScope = Depends(get_project_scope),
    db: AsyncSession = Depends(get_db),
) -> VariantResponse:
    """
    Apply a previously proposed brief revision using optimistic concurrency.
    Returns 409 if the variant has been updated since the proposal was generated
    (base_variant_updated_at no longer matches the current updated_at).
    """
    from app.domain.errors import DomainError
    svc = VariantService(db)
    try:
        current = await svc.get(scope, variant_id)
    except ProjectNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Optimistic concurrency check
    current_updated = current.get("updated_at")
    if current_updated and current_updated != body.base_variant_updated_at:
        raise HTTPException(
            status_code=409,
            detail="Variant was updated since this revision was proposed. Reload and regenerate.",
        )

    fields = {k: v for k, v in {
        "hook": body.hook,
        "hook_delivery_note": body.hook_delivery_note,
        "context": body.context,
        "on_screen_text": body.on_screen_text,
    }.items() if v is not None}

    try:
        await svc.update_brief(scope, variant_id, fields)
    except DomainError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    updated = await svc.get(scope, variant_id)
    return VariantResponse.from_row(updated)


video_router = APIRouter(prefix="/api/videos", tags=["videos"])

_provider = get_intelligence_provider()


@router.get("/{variant_id}", response_model=VariantResponse)
async def get_variant(
    variant_id: UUID,
    scope: ProjectScope = Depends(get_project_scope),
    db: AsyncSession = Depends(get_db),
) -> VariantResponse:
    svc = VariantService(db)
    try:
        row = await svc.get(scope, variant_id)
    except ProjectNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return VariantResponse.from_row(row)


@router.patch("/{variant_id}/brief", response_model=VariantResponse)
async def update_brief(
    variant_id: UUID,
    body: BriefPatchRequest,
    scope: ProjectScope = Depends(get_project_scope),
    db: AsyncSession = Depends(get_db),
) -> VariantResponse:
    svc = VariantService(db)
    try:
        row = await svc.update_brief(scope, variant_id, body.model_dump(exclude_none=True))
    except (ProjectNotFound, DomainError) as exc:
        code = 404 if isinstance(exc, ProjectNotFound) else 409
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    v = await svc.get(scope, variant_id)
    return VariantResponse.from_row(v)


@router.post("/{variant_id}/revise-brief")
async def revise_brief(
    variant_id: UUID,
    body: ReviseBriefRequest,
    scope: ProjectScope = Depends(get_project_scope),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = VariantService(db)
    try:
        result = await svc.revise_brief(scope, variant_id, body.instruction, _provider)
    except (ProjectNotFound, DomainError) as exc:
        code = 404 if isinstance(exc, ProjectNotFound) else 409
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    return result


@router.post("/{variant_id}/approve-for-recording", response_model=VariantResponse)
async def approve_for_recording(
    variant_id: UUID,
    scope: ProjectScope = Depends(get_project_scope),
    db: AsyncSession = Depends(get_db),
) -> VariantResponse:
    svc = VariantService(db)
    try:
        row = await svc.approve_for_recording(scope, variant_id)
    except (ProjectNotFound, DomainError) as exc:
        code = 404 if isinstance(exc, ProjectNotFound) else 409
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    v = await svc.get(scope, variant_id)
    return VariantResponse.from_row(v)


@router.post("/{variant_id}/confirm-recorded", response_model=VariantResponse)
async def confirm_recorded(
    variant_id: UUID,
    scope: ProjectScope = Depends(get_project_scope),
    db: AsyncSession = Depends(get_db),
) -> VariantResponse:
    svc = VariantService(db)
    try:
        row = await svc.confirm_recorded(scope, variant_id)
    except (ProjectNotFound, DomainError) as exc:
        code = 404 if isinstance(exc, ProjectNotFound) else 409
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    v = await svc.get(scope, variant_id)
    return VariantResponse.from_row(v)


@router.post("/{variant_id}/videos", response_model=VideoResponse, status_code=status.HTTP_201_CREATED)
async def create_video(
    variant_id: UUID,
    scope: ProjectScope = Depends(get_project_scope),
    db: AsyncSession = Depends(get_db),
) -> VideoResponse:
    svc = VariantService(db)
    try:
        row = await svc.create_video(scope, variant_id)
    except (ProjectNotFound, DomainError) as exc:
        code = 404 if isinstance(exc, ProjectNotFound) else 409
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    return VideoResponse(**row)


@video_router.get("/{video_id}", response_model=VideoResponse)
async def get_video(
    video_id: UUID,
    scope: ProjectScope = Depends(get_project_scope),
    db: AsyncSession = Depends(get_db),
) -> VideoResponse:
    repo = VideoRepository(db)
    row = await repo.get(scope, video_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")
    return VideoResponse(**row)


@video_router.post("/{video_id}/submit-url", response_model=VideoResponse)
async def submit_url(
    video_id: UUID,
    body: SubmitUrlRequest,
    scope: ProjectScope = Depends(get_project_scope),
    db: AsyncSession = Depends(get_db),
) -> VideoResponse:
    svc = VariantService(db)
    try:
        row = await svc.submit_url(
            scope, video_id, body.url,
            {"video_live": body.video_live, "variable_delivered": body.variable_delivered},
        )
    except (ProjectNotFound, DomainError) as exc:
        code = 404 if isinstance(exc, ProjectNotFound) else 422
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    return VideoResponse(**row)


@video_router.get("/{video_id}/execution-observation", response_model=ObservationResponse | None)
async def get_observation(
    video_id: UUID,
    scope: ProjectScope = Depends(get_project_scope),
    db: AsyncSession = Depends(get_db),
) -> ObservationResponse | None:
    repo = VideoRepository(db)
    row = await repo.get_observation(scope, video_id)
    if not row:
        return None
    return ObservationResponse(**row)


@video_router.put("/{video_id}/execution-observation", response_model=ObservationResponse)
async def upsert_observation(
    video_id: UUID,
    body: ExecutionObservationRequest,
    scope: ProjectScope = Depends(get_project_scope),
    db: AsyncSession = Depends(get_db),
) -> ObservationResponse:
    repo = VideoRepository(db)
    # Verify video belongs to project
    vid = await repo.get(scope, video_id)
    if not vid:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")
    row = await repo.upsert_observation(scope, video_id, body.model_dump(exclude_none=True))
    return ObservationResponse(**row)
