# -*- coding: utf-8 -*-
"""
Shikin review page and associated API
"""

from sqlalchemy import func
import datetime
import random
from flask import render_template, abort, request, jsonify, session

from . import app, ocrfix
from .model import DocSegment, DocSegmentReview, User
from .util import dologin


def get_user_or_abort():
    # if request.remote_addr == '127.0.0.1':
    #     user = 'admin'
    # else:
    user = session.get('username')
    if not user:
        abort(403)

    u = User.query.filter(User.name == user).first()
    if not u:
        abort(403)

    return u


@app.route('/api/reviewcount/<user>')
def review_count(user):
    u = User.query.filter(User.name == user).first()
    if not u:
        return abort(404)
    return jsonify({'user': user, 'count': len(u.reviews)})


@app.route('/api/unreview/<int:segmentid>')
def unreview(segmentid):
    user = get_user_or_abort()

    revid = request.args.get('revid')

    ds = DocSegment.query.filter(DocSegment.id == segmentid).first()
    if not ds:
        abort(404)
    ds.viewcount = max(0, ds.viewcount-1)
    app.dbobj.session.add(ds)
    if not revid or not revid.isdigit():
        app.dbobj.session.commit()
        return
    revid = int(revid)
    old = DocSegmentReview.query.filter(DocSegmentReview.id == revid, DocSegmentReview.user_id == user.id).first()
    if not old:
        abort(404)
    app.dbobj.session.delete(old)
    app.dbobj.session.commit()

    return jsonify({'status': 'ok', 'id': revid})


@app.route('/api/review/<int:segmentid>')
def review_submit(segmentid):
    user = get_user_or_abort()

    ds = DocSegment.query.filter(DocSegment.id == segmentid).first()
    if not ds:
        abort(404)

    text = request.args.get('text')
    skip = request.args.get('skip')

    if text is None and not skip:
        abort(404)

    timestamp = datetime.datetime.now()
    ds.viewcount += 1
    app.dbobj.session.add(ds)

    if skip:
        app.dbobj.session.commit()
        return jsonify({'status': 'ok'})

    old = DocSegmentReview.query\
                          .filter(DocSegmentReview.segment_id == ds.id)\
                          .order_by(DocSegmentReview.rev.desc())\
                          .first()
    if old is not None:
        rev = old.rev + 1
    else:
        rev = 1

    newrev = DocSegmentReview(segment=ds, rev=rev, timestamp=timestamp, user=user, text=text)
    app.dbobj.session.add(newrev)
    app.dbobj.session.commit()

    return jsonify({'status': 'ok', 'id': newrev.id})


@app.route('/api/reviewdata', methods=['GET'])
def reviewdata():
    # Find a random early page with lots of unreviewed items.  This way even
    # with multiple simulteanous users they should get different pages.
    minviewcount = app.dbobj.session.query(func.min(DocSegment.viewcount)).one()[0]

    q = app.dbobj.session.query(DocSegment.doc_id, DocSegment.page)\
                 .filter(DocSegment.ocrtext != None)\
                 .filter(DocSegment.viewcount <= minviewcount)\
                 .distinct()

    pages = list(q.all())

    app.logger.debug("%d pages with segments of only %d views" % (len(pages), minviewcount))

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
            suggests = ocrfix.suggestions(d)
        else:
            txt = d.usertext.text
            suggests = []

        lines = max(len(d.ocrtext.splitlines()), len(txt.splitlines()))

        segdata.append(dict(ocrtext=d.ocrtext, text=txt, segment_id=d.id,
                            x1=d.x1, x2=d.x2, y1=d.y1, y2=d.y2,
                            textlines=lines, docid=docid, page=page+1, suggests=suggests))

    return jsonify(dict(segments=segdata, docid=docid, page=page+1))


@app.route('/review', methods=['GET', 'POST'])
def review():
    """ Review page """
    error = None
    user = None
    if request.method == 'POST':
        user, error = dologin()

    if 'username' in session:
        u = get_user_or_abort()
        uname = u.name
    else:
        uname = None

    return render_template('review.html', user=uname, error=error)
