# -*- coding: utf-8 -*-
"""
Shikin review page
"""

from flask import render_template, abort, request
from . import app, ocrfix
from .model import DocSegment


@app.route('/review', methods=['GET', 'POST'])
def review():
    """ Front page """

    sid = None
    if request.method == 'POST':
        data = request.form
        sid = data['segment_id']

        d = DocSegment.query.filter(DocSegment.id == sid).first()

        if not d:
            abort(404)

        d.review += 1

        if 'save' in data:
            d.usertext = data.get('usertext')

        app.dbobj.session.commit()

    # First search for an exact group match
    d = DocSegment.query\
                  .filter(DocSegment.ocrtext != None)\
                  .order_by(DocSegment.review, DocSegment.doc_id, DocSegment.page, DocSegment.y1)\
                  .first()
    if d is None:
        abort(404)

    if d.usertext is None:
        txt = ocrfix.guess_fix(d.ocrtext)
    else:
        txt = d.usertext

    lines = max(len(d.ocrtext.splitlines()), len(txt.splitlines()))

    return render_template('review.html', doc_id=d.doc_id, page=d.page+1,
                           ocrtext=d.ocrtext, text=txt, segment_id=d.id,
                           x1=d.x1, x2=d.x2, y1=d.y1, y2=d.y2, textlines=lines,
                           lastid=sid)
