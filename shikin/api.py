# -*- coding: utf-8 -*-
"""
Shikin, political donations database.
"""

import os
from flask import send_file, send_from_directory, request, jsonify, abort
from flask.ext import restless
from . import app
from .model import Document, Group, GroupType, DocType, PubType, DocSet, DocSegment
from sqlalchemy.orm.properties import ColumnProperty

from .pdf import pdfimages

# Create the Flask-Restless API manager.
manager = restless.APIManager(app, flask_sqlalchemy_db=app.dbobj)


@app.after_request
def add_no_cache(response):
    if request.method == 'POST' or '/api/' in request.url:
        response.cache_control.no_cache = True
    return response


def check_write_authorization(*args, **kw):
    """
    Check if a given request should be allowed to write to the DB
    """
    # For now only allow local modifications
    if request.remote_addr != '127.0.0.1':
        raise restless.ProcessingException(description='Not Authorized',
                                           code=401)


def raw_columns(table):
    """
    Return the columns which are members of the given table
    """
    cols = []
    for p in table.__mapper__.iterate_properties:
        if isinstance(p, ColumnProperty):
            cols.append(p.key)
    return cols


def _make_raw_api(table):
    ALL_METHODS = ['GET', 'POST', 'PATCH', 'DELETE']
    raw_api_preprocessors = {}
    for update_method in ('POST', 'PUT_MANY', 'PUT_SINGLE', 'DELETE_SINGLE', 'DELETE_MANY'):
        raw_api_preprocessors[update_method] = [check_write_authorization]

    manager.create_api(table, url_prefix='/api/raw',
                       include_columns=raw_columns(table),
                       preprocessors=raw_api_preprocessors,
                       methods=ALL_METHODS, max_results_per_page=50000)


def _make_ro_api(table):
    include_methods = None
    if table == Document:
        include_methods = ['size_str']
    manager.create_api(table, methods=['GET'], max_results_per_page=100,
                       results_per_page=100, include_methods=include_methods)


# Make read-write "raw" APIs for backend use, and read-only apis for frontend
# use
for table in (Document, Group, GroupType, DocType, PubType, DocSet, DocSegment):
    _make_raw_api(table)
    _make_ro_api(table)


@app.route('/doc/cached/<int:docid>/<int:pageno>')
@app.route('/doc/cached/<int:docid>')
def docpdf(docid, pageno=None):
    """Adds the current user as follower of the given user.  Pageno is 1-indexed."""
    doc = Document.query.filter(Document.id == docid).first_or_404()
    path = doc.path
    if path.startswith('/'):
        path = path[1:]
    pdfdir = os.path.abspath(app.config['PDF_DIR'])
    if pageno is not None:
        pdf_fullpath = os.path.join(pdfdir, path)
        app.logger.debug('Returning page %d of %s' % (pageno, pdf_fullpath))
        for img in pdfimages.pdf_images(pdf_fullpath, optimise=False, autorotate=True, firstpage=pageno, lastpage=pageno):
            return send_file(img)
        abort(404)
    else:
        return send_from_directory(pdfdir, path, as_attachment=True)


@app.route('/api/search/<query>')
def searchapi(query):
    if not query:
        return {'values': []}
    q = app.dbobj.session.query(Group.id, Group.name).filter(Group.name.like('%'+query+'%'))
    return jsonify({'values': [{'id': x[0], 'name': x[1]} for x in q.all()]})
