import typing

from db_retry import Transaction
from modern_di import Group, Scope, providers

from app.database import resources as database_resources
from app.repositories.chat_members_repository import ChatMembersRepository
from app.repositories.chats_repository import ChatsRepository
from app.repositories.messages_repository import MessagesRepository
from app.repositories.users_repository import UsersRepository
from app.use_cases.authenticate_user import AuthenticateUserUseCase
from app.use_cases.create_chat import CreateChatUseCase
from app.use_cases.create_message import CreateMessageUseCase
from app.use_cases.delete_message import DeleteMessageUseCase
from app.use_cases.edit_message import EditMessageUseCase
from app.use_cases.fetch_chat import FetchChatUseCase
from app.use_cases.fetch_chats import FetchChatsUseCase
from app.use_cases.fetch_messages import FetchMessagesUseCase
from app.use_cases.mark_read import MarkReadUseCase
from app.use_cases.register_user import RegisterUserUseCase


class Database(Group):
    database_engine = providers.Factory(
        creator=database_resources.create_database_engine,
        cache=providers.CacheSettings(finalizer=database_resources.close_database_engine),
    )
    database_session = providers.Factory(
        scope=Scope.REQUEST,
        creator=database_resources.create_session,
        cache=providers.CacheSettings(finalizer=database_resources.close_session),
    )
    transaction = providers.Factory(
        scope=Scope.REQUEST,
        creator=Transaction,
        kwargs={"session": database_session},
    )


class Repositories(Group, scope=Scope.REQUEST):
    users_repository = providers.Factory(
        creator=UsersRepository,
        kwargs={"session": Database.database_session, "auto_commit": False},
    )
    chats_repository = providers.Factory(
        creator=ChatsRepository,
        kwargs={"session": Database.database_session, "auto_commit": False},
    )
    chat_members_repository = providers.Factory(
        creator=ChatMembersRepository,
        kwargs={"session": Database.database_session, "auto_commit": False},
    )
    messages_repository = providers.Factory(
        creator=MessagesRepository,
        kwargs={"session": Database.database_session, "auto_commit": False},
    )


class UseCases(Group, scope=Scope.REQUEST):
    register_user_use_case = providers.Factory(creator=RegisterUserUseCase)
    authenticate_user_use_case = providers.Factory(creator=AuthenticateUserUseCase)
    create_chat_use_case = providers.Factory(creator=CreateChatUseCase)
    fetch_chat_use_case = providers.Factory(creator=FetchChatUseCase)
    create_message_use_case = providers.Factory(creator=CreateMessageUseCase)
    fetch_messages_use_case = providers.Factory(creator=FetchMessagesUseCase)
    edit_message_use_case = providers.Factory(creator=EditMessageUseCase)
    delete_message_use_case = providers.Factory(creator=DeleteMessageUseCase)
    fetch_chats_use_case = providers.Factory(creator=FetchChatsUseCase)
    mark_read_use_case = providers.Factory(creator=MarkReadUseCase)


ALL_GROUPS: typing.Final[list[type[Group]]] = [Database, Repositories, UseCases]
