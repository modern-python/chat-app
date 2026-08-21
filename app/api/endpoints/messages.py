import typing

import litestar
from litestar import status_codes
from litestar.di import NamedDependency
from litestar.openapi.datastructures import ResponseSpec
from litestar.params import FromPath, FromQuery

from app.api.auth import AuthedRequest
from app.schemas import api as schemas
from app.use_cases.create_message import CreateMessageUseCase
from app.use_cases.delete_message import DeleteMessageUseCase
from app.use_cases.edit_message import EditMessageUseCase
from app.use_cases.fetch_messages import FetchMessagesUseCase


@litestar.post(
    "/chats/{chat_id:int}/messages/",
    responses={
        status_codes.HTTP_200_OK: ResponseSpec(
            data_container=schemas.Message, description="A message already sent with this idempotency key"
        ),
    },
)
async def send_message(
    chat_id: FromPath[int],
    data: schemas.SendMessageRequest,
    request: AuthedRequest,
    create_message_use_case: NamedDependency[CreateMessageUseCase],
) -> litestar.Response[schemas.Message]:
    message, created = await create_message_use_case(actor=request.user, chat_id=chat_id, data=data)
    return litestar.Response(
        content=schemas.Message.model_validate(message),
        status_code=status_codes.HTTP_201_CREATED if created else status_codes.HTTP_200_OK,
    )


@litestar.get("/chats/{chat_id:int}/messages/")
async def list_messages(  # noqa: PLR0913 - each is a distinct Litestar-bound path/query/DI param
    chat_id: FromPath[int],
    request: AuthedRequest,
    fetch_messages_use_case: NamedDependency[FetchMessagesUseCase],
    *,
    before_id: FromQuery[int | None] = None,
    after_id: FromQuery[int | None] = None,
    limit: FromQuery[int] = 50,
) -> schemas.Messages:
    messages: typing.Final = await fetch_messages_use_case(
        actor=request.user, chat_id=chat_id, before_id=before_id, after_id=after_id, limit=limit
    )
    return schemas.Messages.from_models(messages)


@litestar.patch("/messages/{message_id:int}/")
async def edit_message(
    message_id: FromPath[int],
    data: schemas.EditMessageRequest,
    request: AuthedRequest,
    edit_message_use_case: NamedDependency[EditMessageUseCase],
) -> schemas.Message:
    message: typing.Final = await edit_message_use_case(actor=request.user, message_id=message_id, data=data)
    return schemas.Message.model_validate(message)


@litestar.delete("/messages/{message_id:int}/")
async def delete_message(
    message_id: FromPath[int],
    request: AuthedRequest,
    delete_message_use_case: NamedDependency[DeleteMessageUseCase],
) -> None:
    await delete_message_use_case(actor=request.user, message_id=message_id)


ROUTER: typing.Final = litestar.Router(
    path="/api", route_handlers=[send_message, list_messages, edit_message, delete_message]
)
