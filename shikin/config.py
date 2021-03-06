# -*- coding: utf-8 -*-
"""
App config
"""

SQLALCHEMY_DATABASE_URI = 'sqlite:///../db/shikin.db'
DEBUG = True
APP_NAME = 'shikin'
PDF_DIR = 'pdf'
THUMBNAIL_DIR = '/static/thumbnails'
SQLALCHEMY_TRACK_MODIFICATIONS = False

LANGUAGES = {
    'en': 'English',
    'ja': '日本語'
}
