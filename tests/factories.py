from polyfactory.factories.sqlalchemy_factory import SQLAlchemyFactory

from app.database import tables


class UserFactory(SQLAlchemyFactory[tables.UsersTable]):
    __set_association_proxy__ = False
    __set_relationships__ = False
    __check_model__ = False
    id = None
