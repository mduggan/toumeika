# -*- coding: utf-8 -*-
"""
Shikin views.
"""

import os
from flask import render_template, abort, request, redirect, url_for, json, g, session
from sqlalchemy import func
from datetime import timedelta

from . import app
from .model import Document, Group, DocType, PubType, AppConfig
from .config import LANGUAGES


@app.babel.localeselector
def get_locale():
    return request.accept_languages.best_match(LANGUAGES.keys())


@app.before_request
def before_request():
    g.locale = get_locale()
    if not app.secret_key:
        c = AppConfig.query.filter(AppConfig.key == 'secret_key').first()
        if not c:
            abort(500)
        app.secret_key = c.val
    session.permanent = True
    app.permanent_session_lifetime = timedelta(days=7)


def doctype_json():
    return json.dumps({x.id: x.name for x in DocType.query.all()})


def pubtype_json():
    return json.dumps({x.id: x.name for x in PubType.query.all()})


@app.route('/')
def index():
    """ Front page """
    if request.args.get('q'):
        return search(request.args['q'])
    else:
        return render_template('index.html')


@app.route('/about')
def about():
    """ About page """
    return render_template('about.html')


@app.route('/groups')
def groups():
    return render_template('groups.html', doctypes=doctype_json(), pubtypes=pubtype_json(), q=request.args.get('q'))


@app.route('/pubs')
def pubs():
    return render_template('pubs.html', doctypes=doctype_json(), pubtypes=pubtype_json())


@app.route('/years')
def years():
    q = app.dbobj.session.query(Document.year.distinct(), func.count(Document.id))\
                         .order_by(Document.year).group_by(Document.year)
    data = dict(q.all())
    return render_template('years.html', year=data, doctypes=doctype_json(), pubtypes=pubtype_json())


def _group_redir(groupid):
    return redirect(url_for('group', groupid=groupid))


@app.route('/search/<query>')
def search(q):
    """ Front page """
    # First search for an exact group match
    g = Group.query.filter(Group.name == q).first()
    if g is not None:
        return _group_redir(g.id)
    g_query = Group.query.filter(Group.name.like('%' + q + '%'))
    g_count = g_query.count()
    if g_count == 1:
        return _group_redir(g_query.first().id)
    elif g_count > 1:
        return redirect(url_for('groups', q=q))

    return render_template('index.html', nomatch=q)


@app.route('/doc/<int:docid>')
def docpage(docid):
    """ Front page """
    doc = Document.query.filter(Document.id == docid).first()
    if doc is None:
        abort(404)

    pdfpath = doc.path
    if pdfpath.startswith("/"):
        pdfpath = pdfpath[1:]
    thumbnailpath = pdfpath + "_thumb.png"
    pdfpath = os.path.join(app.config["PDF_DIR"], pdfpath)
    thumbnailpath = os.path.join(app.config["THUMBNAIL_DIR"], thumbnailpath)

    return render_template('document.html', pdfurl=doc.url, fname=doc.filename,
                           thumbnail=thumbnailpath, year=doc.year, docid=doc.id,
                           pubtype=doc.docset.pubtype.name,
                           doctype=doc.docset.doctype.name,
                           published=doc.docset.published,
                           group=doc.group.name, group_id=doc.group.id,
                           grouptype=doc.group.type.name,
                           pages=doc.pages, size=doc.size_str, note=doc.note)


@app.route('/group/<int:groupid>')
def group(groupid):
    group = Group.query.filter(Group.id == groupid).first()
    if group is None:
        abort(404)

    doccount = Document.query.filter(Document.group_id == groupid).count()

    return render_template('group.html', groupname=group.name,
                           grouptype=group.type.name, groupid=groupid,
                           doccount=doccount, doctypes=doctype_json(),
                           pubtypes=pubtype_json(), children=len(group.children))
