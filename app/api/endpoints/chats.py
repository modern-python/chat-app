import typing

import litestar
from litestar import status_codes
from litestar.di import NamedDependency
from litestar.params import FromPath

from app.database import tables
from app.schemas import api as schemas
from app.use_cases.create_chat import CreateChatUseCase
from app.use_cases.fetch_chat import FetchChatUseCase


@litestar.post("/chats/")
async def create_chat(
    data: schemas.CreateChatRequest,
    request: litestar.Request[tables.UsersTable, typing.Any, typing.Any],
    create_chat_use_case: NamedDependency[CreateChatUseCase],
) -> litestar.Response[schemas.ChatDetail]:
    chat, created = await create_chat_use_case(request.user, data)
    return litestar.Response(
        content=schemas.ChatDetail.model_validate(chat),
        status_code=status_codes.HTTP_201_CREATED if created else status_codes.HTTP_200_OK,
    )


@litestar.get("/chats/{chat_id:int}/")
async def get_chat(
    chat_id: FromPath[int],
    request: litestar.Request[tables.UsersTable, typing.Any, typing.Any],
    fetch_chat_use_case: NamedDependency[FetchChatUseCase],
) -> schemas.ChatDetail:
    chat: typing.Final = await fetch_chat_use_case(request.user, chat_id)
    return schemas.ChatDetail.model_validate(chat)


ROUTER: typing.Final = litestar.Router(path="/api", route_handlers=[create_chat, get_chat])
