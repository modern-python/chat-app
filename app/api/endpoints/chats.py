import typing

import litestar
from litestar import status_codes
from litestar.di import NamedDependency
from litestar.openapi.datastructures import ResponseSpec
from litestar.params import FromPath

from app.api.auth import AuthedRequest
from app.schemas import api as schemas
from app.use_cases.create_chat import CreateChatUseCase
from app.use_cases.fetch_chat import FetchChatUseCase
from app.use_cases.fetch_chats import FetchChatsUseCase
from app.use_cases.mark_read import MarkReadUseCase


@litestar.post(
    "/chats/",
    responses={
        status_codes.HTTP_200_OK: ResponseSpec(
            data_container=schemas.ChatDetail, description="An existing direct chat for this pair of members"
        ),
    },
)
async def create_chat(
    data: schemas.CreateChatRequest,
    request: AuthedRequest,
    create_chat_use_case: NamedDependency[CreateChatUseCase],
) -> litestar.Response[schemas.ChatDetail]:
    chat, created = await create_chat_use_case(actor=request.user, data=data)
    return litestar.Response(
        content=schemas.ChatDetail.model_validate(chat),
        status_code=status_codes.HTTP_201_CREATED if created else status_codes.HTTP_200_OK,
    )


@litestar.get("/chats/")
async def list_chats(
    request: AuthedRequest,
    fetch_chats_use_case: NamedDependency[FetchChatsUseCase],
) -> schemas.Chats:
    return schemas.Chats.from_models(await fetch_chats_use_case(actor=request.user))


@litestar.get("/chats/{chat_id:int}/")
async def get_chat(
    chat_id: FromPath[int],
    request: AuthedRequest,
    fetch_chat_use_case: NamedDependency[FetchChatUseCase],
) -> schemas.ChatDetail:
    chat: typing.Final = await fetch_chat_use_case(actor=request.user, chat_id=chat_id)
    return schemas.ChatDetail.model_validate(chat)


@litestar.post("/chats/{chat_id:int}/read/", status_code=status_codes.HTTP_200_OK)
async def mark_read(
    chat_id: FromPath[int],
    data: schemas.MarkReadRequest,
    request: AuthedRequest,
    mark_read_use_case: NamedDependency[MarkReadUseCase],
) -> schemas.ChatMember:
    member: typing.Final = await mark_read_use_case(actor=request.user, chat_id=chat_id, data=data)
    return schemas.ChatMember.model_validate(member)


ROUTER: typing.Final = litestar.Router(path="/api", route_handlers=[create_chat, list_chats, get_chat, mark_read])
