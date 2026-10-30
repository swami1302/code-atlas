from sqlalchemy.orm import DeclarativeBase


# Every table class subclasses Base; Alembic reads Base.metadata for autogenerate.
class Base(DeclarativeBase):
    pass
