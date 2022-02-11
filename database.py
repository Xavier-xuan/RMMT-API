from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base

from config import GeneralConfig

engine = create_engine(GeneralConfig.DATABASE_URL, echo=GeneralConfig.DATABASE_LOG)
db_session: scoped_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))
Base = declarative_base()
Base.query = db_session.query_property()