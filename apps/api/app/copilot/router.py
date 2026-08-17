from app.ai.conversation_state import save_conversation_state
from app.ai.conversation_thread import (
    get_or_create_conversation_thread,
)
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import current_user
from app.ai.conversation_control import (
    set_conversation_mode,
)
from app.conversations.evolution_provider import (
    EvolutionSendError,
    send_evolution_text_message,
)

from app.conversations.realtime import (
    publish_conversation_event,
)
from app.conversations.service import (
    mark_human_message_failed,
    mark_human_message_sent,
    prepare_human_message,
    require_conversation_thread,
)
from app.copilot.schemas import (
    CopilotDashboardOverview,
    CopilotAuditListResponse,
    CopilotChatRequest,
    CopilotConversationControlRequest,
    CopilotConversationControlResponse,
    CopilotConversationInsight,
    CopilotChatResponse,
    CopilotPlannerResponse,
    CopilotTask,
    CopilotTaskStateUpdateRequest,
    DailyBriefResponse,
    AppointmentMessageDraftCreateRequest,
    AppointmentMessageDraftResponse,
    AppointmentMessageSendRequest,
    RecallDraftCreateRequest,
    RecallDraftResponse,
    RecallDraftUpdateRequest,
    RecallSendRequest,
)
from app.copilot.dashboard import (
    build_dashboard_overview,
)
from app.copilot.audit import (
    list_copilot_audit_events,
    record_copilot_audit_event,
)
from app.copilot.conversation_insight import (
    build_conversation_insight,
)
from app.copilot.service import (
    answer_copilot_chat,
    build_daily_brief,
    create_appointment_message_draft,
    create_recall_draft,
    update_recall_draft_message,
)
from app.copilot.tasks import (
    upsert_task_state,
)
from app.copilot.planner import (
    build_copilot_tasks,
    build_planner,
)
from app.db import connection
from app.deps import authenticated_clinic_id


router = APIRouter(
    prefix="/copilot",
    tags=["Copilote"],
)


@router.get(
    "/dashboard-overview",
    response_model=CopilotDashboardOverview,
)
async def dashboard_overview(
    current_clinic: UUID = Depends(authenticated_clinic_id),
    user: dict = Depends(current_user),
) -> dict:
    del user

    async with connection() as conn:
        async with conn.cursor() as cur:
            return await build_dashboard_overview(
                cur=cur,
                clinic_id=current_clinic,
            )


@router.get(
    "/daily-brief",
    response_model=DailyBriefResponse,
)
async def daily_brief(
    current_clinic: UUID = Depends(authenticated_clinic_id),
    user: dict = Depends(current_user),
) -> dict:
    async with connection() as conn:
        async with conn.cursor() as cur:
            return await build_daily_brief(
                cur=cur,
                clinic_id=current_clinic,
                user=user,
            )



@router.get(
    "/planner",
    response_model=CopilotPlannerResponse,
)
async def copilot_planner(
    current_clinic: UUID = Depends(authenticated_clinic_id),
    user: dict = Depends(current_user),
) -> dict:
    """
    Retourne l'état opérationnel courant de la clinique.

    Cet endpoint est strictement en lecture seule.
    """

    async with connection() as conn:
        async with conn.cursor() as cur:
            return await build_planner(
                cur=cur,
                clinic_id=current_clinic,
            )


@router.get(
    "/tasks",
    response_model=list[CopilotTask],
)
async def copilot_tasks(
    current_clinic: UUID = Depends(authenticated_clinic_id),
    user: dict = Depends(current_user),
) -> list[dict]:
    """
    Retourne les tâches opérationnelles unifiées du Copilote.

    Cet endpoint est strictement en lecture seule.
    """

    async with connection() as conn:
        async with conn.cursor() as cur:
            return await build_copilot_tasks(
                cur=cur,
                clinic_id=current_clinic,
            )


@router.patch(
    "/tasks/{task_key:path}",
)
async def update_copilot_task_state(
    task_key: str,
    payload: CopilotTaskStateUpdateRequest,
    current_clinic: UUID = Depends(authenticated_clinic_id),
    user: dict = Depends(current_user),
) -> dict:
    async with connection() as conn:
        async with conn.cursor() as cur:
            state = await upsert_task_state(
                cur=cur,
                clinic_id=current_clinic,
                task_key=task_key,
                status=payload.status,
                snoozed_until=payload.snoozed_until,
                assigned_user_id=(
                    user["id"]
                    if payload.assign_to_me
                    else None
                ),
            )

        await conn.commit()

    event_type = (
        "copilot.task.completed"
        if payload.status == "completed"
        else "copilot.task.updated"
    )

    await publish_conversation_event(
        clinic_id=current_clinic,
        event_type=event_type,
        data={
            "task_key": task_key,
            "status": payload.status,
            "assigned_user_id": state.get(
                "assigned_user_id"
            ),
            "snoozed_until": state.get(
                "snoozed_until"
            ),
            "completed_at": state.get(
                "completed_at"
            ),
        },
    )

    return state


@router.post(
    "/chat",
    response_model=CopilotChatResponse,
)
async def copilot_chat(
    payload: CopilotChatRequest,
    current_clinic: UUID = Depends(authenticated_clinic_id),
    user: dict = Depends(current_user),
) -> dict:
    async with connection() as conn:
        async with conn.cursor() as cur:
            return await answer_copilot_chat(
                cur=cur,
                clinic_id=current_clinic,
                message=payload.message,
            )


@router.post(
    "/appointment-message-drafts",
    response_model=AppointmentMessageDraftResponse,
    status_code=201,
)
async def create_appointment_message_draft_endpoint(
    payload: AppointmentMessageDraftCreateRequest,
    current_clinic: UUID = Depends(authenticated_clinic_id),
    user: dict = Depends(current_user),
) -> dict:
    async with connection() as conn:
        async with conn.cursor() as cur:
            try:
                draft = await create_appointment_message_draft(
                    cur=cur,
                    clinic_id=current_clinic,
                    patient_id=payload.patient_id,
                    appointment_id=payload.appointment_id,
                    message_kind=payload.message_kind,
                    message=payload.message,
                    created_by_user_id=user["id"],
                )

            except LookupError as exc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=str(exc),
                ) from exc

            except RuntimeError as exc:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=str(exc),
                ) from exc

            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(exc),
                ) from exc

            await record_copilot_audit_event(
                cur=cur,
                clinic_id=current_clinic,
                patient_id=draft["patient_id"],
                actor_user_id=user["id"],
                action_type="appointment_message_draft_created",
                result="success",
                entity_type="communication_event",
                entity_id=draft["id"],
                after_data={
                    "status": draft["payload"].get("status"),
                    "message_kind": draft["payload"].get(
                        "message_kind"
                    ),
                },
                metadata={
                    "actor_label": (
                        user.get("full_name")
                        or user.get("email")
                        or "Utilisateur"
                    ),
                    "source": "copilot_appointment_message",
                    "draft_id": str(draft["id"]),
                    "appointment_id": str(
                        draft["appointment_id"]
                    ),
                },
            )

        await conn.commit()

    return draft


@router.post(
    "/appointment-message-drafts/send",
    status_code=201,
)
async def send_appointment_message_draft_endpoint(
    payload: AppointmentMessageSendRequest,
    current_clinic: UUID = Depends(authenticated_clinic_id),
    user: dict = Depends(current_user),
) -> dict:
    """
    Valide humainement puis envoie un brouillon WhatsApp
    lié à un rendez-vous.

    Aucun workflow conversationnel de réservation n'est
    démarré par cet envoi.
    """

    user_id = user.get("id")

    if not isinstance(user_id, UUID):
        user_id = UUID(str(user_id))

    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id
                FROM conversation_threads
                WHERE clinic_id = %s
                  AND patient_id = %s
                  AND channel = 'whatsapp'
                  AND status = 'open'
                  AND provider_instance IS NOT NULL
                ORDER BY
                    last_message_at DESC NULLS LAST,
                    updated_at DESC,
                    id DESC
                LIMIT 1
                """,
                (
                    current_clinic,
                    payload.patient_id,
                ),
            )

            thread_row = await cur.fetchone()

            await cur.execute(
                """
                SELECT id
                FROM communication_events
                WHERE id = %s
                  AND clinic_id = %s
                  AND patient_id = %s
                  AND appointment_id = %s
                  AND channel = 'whatsapp'
                  AND direction = 'outbound'
                  AND event_type = 'appointment_message_draft'
                  AND payload->>'message_kind' = %s
                  AND payload->>'status' = 'draft'
                LIMIT 1
                """,
                (
                    payload.draft_id,
                    current_clinic,
                    payload.patient_id,
                    payload.appointment_id,
                    payload.message_kind,
                ),
            )

            if await cur.fetchone() is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Ce brouillon n'est plus disponible "
                        "pour validation."
                    ),
                )

            if thread_row is None:
                await cur.execute(
                    """
                    SELECT phone
                    FROM patients
                    WHERE id = %s
                      AND clinic_id = %s
                    LIMIT 1
                    """,
                    (
                        payload.patient_id,
                        current_clinic,
                    ),
                )

                patient_row = await cur.fetchone()

                patient_phone = (
                    str(
                        patient_row.get("phone")
                        if patient_row
                        else ""
                    ).strip()
                )

                if not patient_phone:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "Aucun numéro WhatsApp n'est "
                            "disponible pour ce patient."
                        ),
                    )

                await cur.execute(
                    """
                    SELECT provider_instance
                    FROM clinic_integrations
                    WHERE clinic_id = %s
                      AND LOWER(BTRIM(provider)) = 'evolution'
                      AND active = TRUE
                    ORDER BY
                        updated_at DESC,
                        created_at DESC
                    LIMIT 1
                    """,
                    (current_clinic,),
                )

                integration_row = await cur.fetchone()

                provider_instance = (
                    str(
                        integration_row.get(
                            "provider_instance"
                        )
                        if integration_row
                        else ""
                    ).strip()
                )

                if not provider_instance:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "Aucune intégration Evolution active "
                            "n'est configurée pour cette clinique."
                        ),
                    )

                thread_row = (
                    await get_or_create_conversation_thread(
                        cur=cur,
                        clinic_id=current_clinic,
                        patient_id=payload.patient_id,
                        channel="whatsapp",
                        sender_phone=patient_phone,
                        provider="evolution",
                        provider_instance=provider_instance,
                        external_thread_id=None,
                    )
                )

            thread_id = thread_row["id"]

            thread, prepared_message = (
                await prepare_human_message(
                    cur=cur,
                    clinic_id=current_clinic,
                    thread_id=thread_id,
                    user_id=user_id,
                    body=payload.message,
                )
            )

        await conn.commit()

    try:
        provider_result = (
            await send_evolution_text_message(
                instance=thread["provider_instance"],
                sender_phone=thread["sender_phone"],
                text=prepared_message["body"],
            )
        )

    except EvolutionSendError as exc:
        async with connection() as conn:
            async with conn.cursor() as cur:
                failed_message = (
                    await mark_human_message_failed(
                        cur=cur,
                        clinic_id=current_clinic,
                        message_id=prepared_message["id"],
                        error=str(exc),
                        status_code=exc.status_code,
                        response_body=exc.response_body,
                    )
                )

                await cur.execute(
                    """
                    UPDATE communication_events
                    SET payload = jsonb_set(
                        payload,
                        '{status}',
                        '"failed"'::jsonb,
                        TRUE
                    )
                    WHERE id = %s
                      AND clinic_id = %s
                    """,
                    (
                        payload.draft_id,
                        current_clinic,
                    ),
                )

                await record_copilot_audit_event(
                    cur=cur,
                    clinic_id=current_clinic,
                    patient_id=payload.patient_id,
                    actor_user_id=user_id,
                    action_type="appointment_message_send",
                    result="failed",
                    entity_type="communication_event",
                    entity_id=payload.draft_id,
                    metadata={
                        "actor_label": (
                            user.get("full_name")
                            or user.get("email")
                            or "Utilisateur"
                        ),
                        "source": (
                            "copilot_appointment_message"
                        ),
                        "draft_id": str(
                            payload.draft_id
                        ),
                        "appointment_id": str(
                            payload.appointment_id
                        ),
                        "message_kind": (
                            payload.message_kind
                        ),
                        "error": str(exc),
                    },
                )

            await conn.commit()

        await publish_conversation_event(
            clinic_id=current_clinic,
            event_type="conversation.message.failed",
            data={
                "thread_id": str(thread_id),
                "message": failed_message,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    async with connection() as conn:
        async with conn.cursor() as cur:
            sent_message = await mark_human_message_sent(
                cur=cur,
                clinic_id=current_clinic,
                message_id=prepared_message["id"],
                external_id=provider_result["external_id"],
                provider_response=provider_result["response"],
            )

            await cur.execute(
                """
                UPDATE communication_events
                SET
                    external_id = %s,
                    payload = jsonb_set(
                        payload,
                        '{status}',
                        '"sent"'::jsonb,
                        TRUE
                    )
                WHERE id = %s
                  AND clinic_id = %s
                """,
                (
                    provider_result["external_id"],
                    payload.draft_id,
                    current_clinic,
                ),
            )

            await record_copilot_audit_event(
                cur=cur,
                clinic_id=current_clinic,
                patient_id=payload.patient_id,
                actor_user_id=user_id,
                action_type="appointment_message_sent",
                result="success",
                entity_type="communication_event",
                entity_id=payload.draft_id,
                after_data={
                    "status": "sent",
                    "message_kind": payload.message_kind,
                },
                metadata={
                    "actor_label": (
                        user.get("full_name")
                        or user.get("email")
                        or "Utilisateur"
                    ),
                    "source": (
                        "copilot_appointment_message"
                    ),
                    "draft_id": str(payload.draft_id),
                    "appointment_id": str(
                        payload.appointment_id
                    ),
                    "message_kind": (
                        payload.message_kind
                    ),
                    "thread_id": str(thread_id),
                },
            )

            task_key = (
                f"confirmation:{payload.appointment_id}"
                if payload.message_kind
                == "pending_confirmation"
                else f"no_show:{payload.appointment_id}"
            )

            await upsert_task_state(
                cur=cur,
                clinic_id=current_clinic,
                task_key=task_key,
                status="completed",
                snoozed_until=None,
                assigned_user_id=None,
            )

        await conn.commit()

    await publish_conversation_event(
        clinic_id=current_clinic,
        event_type="conversation.message.sent",
        data={
            "thread_id": str(thread_id),
            "message": sent_message,
        },
    )

    return {
        "status": "sent",
        "draft_id": payload.draft_id,
        "thread_id": thread_id,
        "message": sent_message,
    }


@router.post(
    "/recall/drafts",
    response_model=RecallDraftResponse,
    status_code=201,
)
async def create_recall_draft_endpoint(
    payload: RecallDraftCreateRequest,
    current_clinic: UUID = Depends(authenticated_clinic_id),
    user: dict = Depends(current_user),
) -> dict:
    async with connection() as conn:
        async with conn.cursor() as cur:
            draft = await create_recall_draft(
                cur=cur,
                clinic_id=current_clinic,
                patient_id=payload.patient_id,
                appointment_id=payload.appointment_id,
                message=payload.message,
                candidate_score=payload.candidate_score,
                match_level=payload.match_level,
                reasons=payload.reasons,
                created_by_user_id=user["id"],
            )

        await conn.commit()

    return draft



@router.patch(
    "/recall/drafts/{draft_id}",
    response_model=RecallDraftResponse,
)
async def update_recall_draft_endpoint(
    draft_id: UUID,
    payload: RecallDraftUpdateRequest,
    current_clinic: UUID = Depends(authenticated_clinic_id),
    user: dict = Depends(current_user),
) -> dict:
    async with connection() as conn:
        async with conn.cursor() as cur:
            try:
                update_result = await update_recall_draft_message(
                    cur=cur,
                    clinic_id=current_clinic,
                    draft_id=draft_id,
                    message=payload.message,
                )

                before_draft = update_result["before"]
                updated_draft = update_result["after"]

            except LookupError as exc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=str(exc),
                ) from exc

            except RuntimeError as exc:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=str(exc),
                ) from exc

            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(exc),
                ) from exc

            await record_copilot_audit_event(
                cur=cur,
                clinic_id=current_clinic,
                patient_id=updated_draft["patient_id"],
                actor_user_id=user["id"],
                action_type="recall_draft_updated",
                result="success",
                entity_type="communication_event",
                entity_id=updated_draft["id"],
                before_data={
                    "message": (
                        before_draft["payload"].get("message")
                        if before_draft
                        else None
                    ),
                },
                after_data={
                    "message": updated_draft["payload"].get(
                        "message"
                    ),
                },
                metadata={
                    "actor_label": (
                        user.get("full_name")
                        or user.get("email")
                        or "Utilisateur"
                    ),
                    "source": "copilot_recall",
                    "draft_id": str(updated_draft["id"]),
                },
            )

        await conn.commit()

    return updated_draft


@router.post(
    "/recall/send",
    status_code=201,
)
async def send_recall_proposal(
    payload: RecallSendRequest,
    current_clinic: UUID = Depends(authenticated_clinic_id),
    user: dict = Depends(current_user),
) -> dict:
    user_id = user.get("id")

    if not isinstance(user_id, UUID):
        user_id = UUID(str(user_id))

    is_slot_recall = payload.appointment_id is not None

    if is_slot_recall:
        if payload.practitioner_id is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Le créneau n'a pas de praticien attribué. "
                    "Attribuez un praticien avant l'envoi."
                ),
            )

        if payload.start_at is None or payload.end_at is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Le créneau de rappel doit avoir une date "
                    "de début et une date de fin."
                ),
            )

    # --------------------------------------------------------
    # Retrouver la conversation WhatsApp du patient
    # + vérifier que le brouillon existe toujours
    # --------------------------------------------------------

    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id
                FROM conversation_threads
                WHERE clinic_id = %s
                  AND patient_id = %s
                  AND channel = 'whatsapp'
                  AND status = 'open'
                  AND provider_instance IS NOT NULL
                ORDER BY
                    last_message_at DESC NULLS LAST,
                    updated_at DESC,
                    id DESC
                LIMIT 1
                """,
                (
                    current_clinic,
                    payload.patient_id,
                ),
            )

            thread_row = await cur.fetchone()

            await cur.execute(
                """
                SELECT id
                FROM communication_events
                WHERE id = %s
                  AND clinic_id = %s
                  AND patient_id = %s
                  AND appointment_id IS NOT DISTINCT FROM %s
                  AND channel = 'whatsapp'
                  AND direction = 'outbound'
                  AND event_type = 'recall_draft'
                  AND payload->>'status' = 'draft'
                LIMIT 1
                """,
                (
                    payload.draft_id,
                    current_clinic,
                    payload.patient_id,
                    payload.appointment_id,
                ),
            )

            if await cur.fetchone() is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Ce brouillon n'est plus disponible "
                        "pour validation."
                    ),
                )

            if thread_row is None:
                if is_slot_recall:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "Aucune conversation WhatsApp ouverte "
                            "n'est disponible pour ce patient."
                        ),
                    )

                await cur.execute(
                    """
                    SELECT phone
                    FROM patients
                    WHERE id = %s
                      AND clinic_id = %s
                    LIMIT 1
                    """,
                    (
                        payload.patient_id,
                        current_clinic,
                    ),
                )

                patient_row = await cur.fetchone()

                patient_phone = (
                    str(patient_row.get("phone") or "").strip()
                    if patient_row
                    else ""
                )

                if not patient_phone:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "Aucun numéro WhatsApp n'est "
                            "disponible pour ce patient."
                        ),
                    )

                await cur.execute(
                    """
                    SELECT provider_instance
                    FROM clinic_integrations
                    WHERE clinic_id = %s
                      AND LOWER(BTRIM(provider)) = 'evolution'
                      AND active = TRUE
                    ORDER BY
                        updated_at DESC,
                        created_at DESC
                    LIMIT 1
                    """,
                    (current_clinic,),
                )

                integration_row = await cur.fetchone()

                provider_instance = (
                    str(
                        integration_row.get(
                            "provider_instance"
                        )
                        or ""
                    ).strip()
                    if integration_row
                    else ""
                )

                if not provider_instance:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "Aucune intégration Evolution active "
                            "n'est configurée pour cette clinique."
                        ),
                    )

                thread_row = (
                    await get_or_create_conversation_thread(
                        cur=cur,
                        clinic_id=current_clinic,
                        patient_id=payload.patient_id,
                        channel="whatsapp",
                        sender_phone=patient_phone,
                        provider="evolution",
                        provider_instance=provider_instance,
                        external_thread_id=None,
                    )
                )

            thread_id = thread_row["id"]

            thread, prepared_message = await prepare_human_message(
                cur=cur,
                clinic_id=current_clinic,
                thread_id=thread_id,
                user_id=user_id,
                body=payload.message,
            )

        await conn.commit()

    # --------------------------------------------------------
    # IMPORTANT :
    # on prépare l'état AVANT l'envoi externe.
    # Ainsi une réponse très rapide OUI/NON est comprise.
    # --------------------------------------------------------

    confirmation_context = None

    if is_slot_recall:
        confirmation_context = {
            "intent": "book_appointment",
            "active_workflow": "book_appointment",
            "source": "copilot_recall",
            "recall_draft_id": str(payload.draft_id),
            "released_appointment_id": str(
                payload.appointment_id
            ),
            "practitioner_id": str(
                payload.practitioner_id
            ),
            "treatment_id": (
                str(payload.treatment_id)
                if payload.treatment_id
                else None
            ),
            "start_at": payload.start_at.isoformat(),
            "end_at": payload.end_at.isoformat(),
            "requested_date_text": (
                payload.start_at.strftime("%d/%m/%Y")
            ),
            "requested_time_text": (
                payload.start_at.strftime("%H:%M")
            ),
            "confirmed": False,
        }

        await save_conversation_state(
            clinic_id=current_clinic,
            patient_id=payload.patient_id,
            channel="whatsapp",
            state="waiting_for_confirmation",
            context=confirmation_context,
        )

    # --------------------------------------------------------
    # Envoi Evolution WhatsApp
    # --------------------------------------------------------

    try:
        provider_result = await send_evolution_text_message(
            instance=thread["provider_instance"],
            sender_phone=thread["sender_phone"],
            text=prepared_message["body"],
        )

    except EvolutionSendError as exc:
        async with connection() as conn:
            async with conn.cursor() as cur:
                failed_message = await mark_human_message_failed(
                    cur=cur,
                    clinic_id=current_clinic,
                    message_id=prepared_message["id"],
                    error=str(exc),
                    status_code=exc.status_code,
                    response_body=exc.response_body,
                )

                await cur.execute(
                    """
                    UPDATE communication_events
                    SET payload = jsonb_set(
                        payload,
                        '{status}',
                        '"failed"'::jsonb,
                        TRUE
                    )
                    WHERE id = %s
                      AND clinic_id = %s
                    """,
                    (
                        payload.draft_id,
                        current_clinic,
                    ),
                )

                await record_copilot_audit_event(
                    cur=cur,
                    clinic_id=current_clinic,
                    patient_id=payload.patient_id,
                    actor_user_id=user_id,
                    action_type="recall_proposal_send",
                    result="failed",
                    entity_type=(
                        "appointment"
                        if is_slot_recall
                        else "communication_event"
                    ),
                    entity_id=(
                        payload.appointment_id
                        if is_slot_recall
                        else payload.draft_id
                    ),
                    metadata={
                        "actor_label": (
                            user.get("full_name")
                            or user.get("email")
                            or "Utilisateur"
                        ),
                        "source": "copilot_recall",
                        "draft_id": str(payload.draft_id),
                        "error": str(exc),
                    },
                )

            await conn.commit()

        if confirmation_context is not None:
            await save_conversation_state(
                clinic_id=current_clinic,
                patient_id=payload.patient_id,
                channel="whatsapp",
                state="completed",
                context={
                    **confirmation_context,
                    "send_failed": True,
                },
            )

        await publish_conversation_event(
            clinic_id=current_clinic,
            event_type="conversation.message.failed",
            data={
                "thread_id": str(thread_id),
                "message": failed_message,
            },
        )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    # --------------------------------------------------------
    # Marquer message + draft comme envoyés + audit
    # --------------------------------------------------------

    async with connection() as conn:
        async with conn.cursor() as cur:
            sent_message = await mark_human_message_sent(
                cur=cur,
                clinic_id=current_clinic,
                message_id=prepared_message["id"],
                external_id=provider_result["external_id"],
                provider_response=provider_result["response"],
            )

            await cur.execute(
                """
                UPDATE communication_events
                SET
                    external_id = %s,
                    payload = jsonb_set(
                        payload,
                        '{status}',
                        '"sent"'::jsonb,
                        TRUE
                    )
                WHERE id = %s
                  AND clinic_id = %s
                """,
                (
                    provider_result["external_id"],
                    payload.draft_id,
                    current_clinic,
                ),
            )

            await record_copilot_audit_event(
                cur=cur,
                clinic_id=current_clinic,
                patient_id=payload.patient_id,
                actor_user_id=user_id,
                action_type="recall_proposal_sent",
                result="success",
                entity_type=(
                    "appointment"
                    if is_slot_recall
                    else "communication_event"
                ),
                entity_id=(
                    payload.appointment_id
                    if is_slot_recall
                    else payload.draft_id
                ),
                after_data=(
                    {
                        "status": "waiting_for_confirmation",
                        "start_at": payload.start_at,
                        "end_at": payload.end_at,
                    }
                    if is_slot_recall
                    else {
                        "status": "sent",
                    }
                ),
                metadata={
                    "actor_label": (
                        user.get("full_name")
                        or user.get("email")
                        or "Utilisateur"
                    ),
                    "source": "copilot_recall",
                    "draft_id": str(payload.draft_id),
                    "thread_id": str(thread_id),
                },
            )

        await conn.commit()

    await publish_conversation_event(
        clinic_id=current_clinic,
        event_type="conversation.message.sent",
        data={
            "thread_id": str(thread_id),
            "message": sent_message,
        },
    )

    return {
        "status": "sent",
        "draft_id": payload.draft_id,
        "thread_id": thread_id,
        "waiting_for_confirmation": is_slot_recall,
        "message": sent_message,
    }


@router.get(
    "/conversations/{thread_id}/insight",
    response_model=CopilotConversationInsight,
)
async def conversation_insight(
    thread_id: UUID,
    current_clinic: UUID = Depends(authenticated_clinic_id),
    user: dict = Depends(current_user),
) -> dict:
    del user

    async with connection() as conn:
        async with conn.cursor() as cur:
            insight = await build_conversation_insight(
                cur=cur,
                clinic_id=current_clinic,
                thread_id=thread_id,
            )

    if insight is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation introuvable.",
        )

    return insight


@router.get(
    "/conversations/{thread_id}/audit",
    response_model=CopilotAuditListResponse,
)
async def conversation_audit(
    thread_id: UUID,
    current_clinic: UUID = Depends(authenticated_clinic_id),
    user: dict = Depends(current_user),
) -> dict:
    del user
    async with connection() as conn:
        async with conn.cursor() as cur:
            await require_conversation_thread(cur=cur, clinic_id=current_clinic, thread_id=thread_id)
            items = await list_copilot_audit_events(cur=cur, clinic_id=current_clinic, thread_id=thread_id)
    return {"thread_id": thread_id, "items": items}


@router.patch(
    "/conversations/{thread_id}/control",
    response_model=CopilotConversationControlResponse,
)
async def conversation_control(
    thread_id: UUID,
    payload: CopilotConversationControlRequest,
    current_clinic: UUID = Depends(authenticated_clinic_id),
    user: dict = Depends(current_user),
) -> dict:
    user_id = user.get("id")

    if not isinstance(user_id, UUID):
        user_id = UUID(str(user_id))

    async with connection() as conn:
        async with conn.cursor() as cur:
            thread = await require_conversation_thread(
                cur=cur,
                clinic_id=current_clinic,
                thread_id=thread_id,
            )

            control = await set_conversation_mode(
                cur=cur,
                clinic_id=current_clinic,
                channel=thread["channel"],
                sender_phone=thread["sender_phone"],
                mode=payload.mode,
                patient_id=thread.get("patient_id"),
                user_id=(user_id if payload.mode == "human_active" else None),
            )
            await record_copilot_audit_event(
                cur=cur, clinic_id=current_clinic, thread_id=thread_id, patient_id=thread.get("patient_id"), actor_user_id=user_id,
                action_type=("human_takeover" if payload.mode == "human_active" else "copilot_reactivated"), result="success",
                entity_type="conversation", entity_id=thread_id, before_data={"mode": thread.get("control_mode")}, after_data={"mode": control["mode"]},
                metadata={"actor_label": user.get("full_name") or user.get("email") or "Utilisateur"},
            )

        await conn.commit()

    response = {
        "thread_id": thread_id,
        "mode": control["mode"],
        "taken_over_by_user_id": control.get(
            "taken_over_by_user_id"
        ),
        "taken_over_at": control.get("taken_over_at"),
    }

    await publish_conversation_event(
        clinic_id=current_clinic,
        event_type="conversation.control.changed",
        data={
            "thread_id": str(thread_id),
            "mode": control["mode"],
            "taken_over_by_user_id": (
                str(control["taken_over_by_user_id"])
                if control.get("taken_over_by_user_id")
                else None
            ),
            "taken_over_at": (
                control["taken_over_at"].isoformat()
                if control.get("taken_over_at")
                else None
            ),
        },
    )

    return response
