# -*- coding: utf-8 -*-
"""
Shikin, political donations database.
"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy, BaseQuery
from flask_babel import Babel

# fix flask-restless bug.. https://github.com/jfinkels/flask-restless/issues/702
def _limit(self):
    return self.limit()

setattr(BaseQuery, '_limit', _limit)

from . import config

# create our little application
app = Flask(config.APP_NAME)
app.config.from_object(config)
app.config.from_envvar('SHIKIN_SETTINGS', silent=True)
app.dbobj = SQLAlchemy(app)
app.babel = Babel(app)

from . import views
from . import api
from . import pageapi
from . import review
