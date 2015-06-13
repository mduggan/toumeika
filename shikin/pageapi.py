"""
Pager API calls for use with DataTables on the frontend
"""

from flask import request, jsonify
from . import app
from .model import Group, Document, GroupType  # , DocType, PubType, DocSet


from sqlalchemy import desc, func


def _order_by_name(isdesc):
    return Group.name.desc() if isdesc else Group.name


def _order_by_type_name(isdesc):
    return GroupType.name.desc() if isdesc else GroupType.name


def _order_by_doccount(isdesc):
    x = func.count(Group.docs)
    return desc(x) if isdesc else x


_group_order_funcs = {
    'name': _order_by_name,
    'typename': _order_by_type_name,
    'doccount': _order_by_doccount,
}


@app.route('/api/summary/group/<int:parentid>/children')
@app.route('/api/summary/group')
def group_pager(parentid=None):
    args = request.args
    count = int(args.get('length') or '10')
    start = int(args.get('start') or '0')

    allgroupquery = Group.query
    if parentid is not None:
        allgroupquery = allgroupquery.filter(Group.parent_id == parentid)
    allgroupcount = allgroupquery.count()

    # TODO. sorting, searching.
    q = Group.query.join(Document).join(GroupType).add_columns(func.count(Document.id)).group_by(Group.id)  # .filter(..)

    if parentid is not None:
        q = q.filter(Group.parent_id == parentid)

    for i in range(100):
        odir_s = 'order[%d][dir]' % i
        ocol_s = 'order[%d][column]' % i
        if not (odir_s in args and ocol_s in args):
            break
        isdesc = args[odir_s] == 'desc'
        cno = int(args[ocol_s])
        cname = args['columns[%d][data]' % cno]
        q = q.order_by(_group_order_funcs[cname](isdesc))

    sval = args.get('search[value]')
    if sval:
        q = q.filter(Group.name.like('%'+sval+'%'))

    q_offset = q.offset(start).limit(count)

    data = list([{'id': x.id, 'name': x.name, 'typename': x.type.name,
                  'doccount': c, 'minyear': x.minyear,
                  'maxyear': x.maxyear} for x, c in q_offset.all()])

    result = {'draw': args.get('draw'), 'recordsTotal': allgroupcount,
              'recordsFiltered': q.count(), 'data': data}

    return jsonify(result)


@app.route('/api/summary/year')
def year_summary():
    q = app.dbobj.session.query(Document.year.distinct(), func.count(Document.id))\
                 .order_by(Document.year).group_by(Document.year)
    data = dict(q.all())
    return jsonify(data)
