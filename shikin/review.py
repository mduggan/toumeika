# -*- coding: utf-8 -*-
"""
Shikin review page and associated API
"""

from flask import render_template, abort, request, jsonify
from . import app, ocrfix
from .model import DocSegment, DocSegmentReview, User

from sqlalchemy import func

import datetime
import random
import json


@app.route('/api/reviewcount/<user>')
def review_count(user):
    u = User.query.filter(User.name == user).first()
    if not u:
        return abort(404)
    return jsonify({'user': user, 'count': len(u.reviews)})


@app.route('/api/review/<int:segmentid>')
def review_submit(segmentid):
    user = None
    if request.remote_addr == '127.0.0.1':
        user = 'admin'
    else:
        # TODO: users, logins, etc.
        abort(403)

    u = User.query.filter(User.name == user).first()
    if not u:
        abort(404)

    ds = DocSegment.query.filter(DocSegment.id == segmentid).first()
    if not ds:
        abort(404)

    text = request.params.get('text')
    if text is None:
        abort(404)

    oldrev = request.params.get('oldrev')
    timestamp = datetime.datetime.now()

    # be sure we're inside a transaction for the next bit..
    app.dbobj.session.begin()

    if oldrev is not None:
        rev = 1
    else:
        old = DocSegmentReview.query.filter(DocSegmentReview.segment_id == ds.id).first()
        if not old:
            abort(404)
        rev = old.rev + 1

    newrev = DocSegmentReview(segment=ds, rev=rev, timestamp=timestamp, user=u, text=text)
    app.dbobj.session.add(newrev)
    app.dbobj.session.commit()

    return jsonify({'status': 'ok', 'id': newrev.id})


@app.route('/review', methods=['GET'])
def review():
    """ Front page """
    # Find a random early page with lots of unreviewed items.  This way even
    # with multiple simulteanous users they should get different pages.
    minviewcount = app.dbobj.session.query(func.min(DocSegment.viewcount)).one()[0]

    q = app.dbobj.session.query(DocSegment.doc_id, DocSegment.page)\
                 .filter(DocSegment.ocrtext != None)\
                 .filter(DocSegment.viewcount <= minviewcount)\
                 .distinct()

    pages = list(q.all())

    app.logger.debug("%d pages with segments of only %d views")

    # FIXME: this kinda works, but as all the pages get reviewed it will tend
    # toward giving all users the same page.  not really a problem until I have
    # more than 1 user.
    docid, page = random.choice(pages)
    q = DocSegment.query.filter(DocSegment.doc_id == docid)\
                        .filter(DocSegment.page == page)\
                        .filter(DocSegment.viewcount <= minviewcount)

    segments = q.all()
    if not segments:
        abort(404)

    segdata = []
    for d in segments:
        if d.usertext is None:
            txt = ocrfix.guess_fix(d.ocrtext)
        else:
            txt = d.usertext

        lines = max(len(d.ocrtext.splitlines()), len(txt.splitlines()))

        segdata.append(dict(ocrtext=d.ocrtext, text=txt, segment_id=d.id,
                            x1=d.x1, x2=d.x2, y1=d.y1, y2=d.y2,
                            textlines=lines))

    return render_template('review.html', doc_id=docid, page=page+1, segdata=json.dumps(segdata))
