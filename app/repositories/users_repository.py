from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from advanced_alchemy.service import SQLAlchemyAsyncRepositoryService

from app.database import tables


class UsersRepository(SQLAlchemyAsyncRepositoryService[tables.UsersTable]):
    class BaseRepository(SQLAlchemyAsyncRepository[tables.UsersTable]):
        model_type = tables.UsersTable

    repository_type = BaseRepository
