# -*- coding: utf-8 -*-
"""
Shikin, political donations database.
"""

from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.babel import Babel

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
