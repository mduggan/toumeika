#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import json
import re
import logging
import requests
import subprocess
from datetime import date
from argparse import ArgumentParser

from toollib import metautil, DATE_RE, YEAR_RE, year_to_western

# Note the full-width brackets and slash.
MULTIPART_RE = re.compile(u'^(.*)(（.*／.*）.*|（その.*）)')

# Simplify a couple of docset types
DOCSETTYPE_MAPPING = {
    u'政党の届出事項の異動の届出': u'異動の届出',
    u'政治団体の届出事項の異動の届出': u'異動の届出',
}


def title_date(title):
    result = DATE_RE.search(title)

    if result is None:
        import pdb; pdb.set_trace()
        raise ValueError("Title didn't match expected format: %s" % title)

    (emp, year, month, day) = result.groups()[:4]
    year = int(year.strip())
    month = int(month.strip())
    day = int(day.strip())
    year = year_to_western(emp, year)

    return date(year, month, day)


def makefilter(field, val, op='=='):
    fparams = {'filter': [{'name': field, 'op': op, 'val': val}]}
    return fparams


def _get_all(s, api_root, otype):
    LIST_ALL_PARAM = {'results_per_page': '50000'}
    objs = s.get(api_root + otype, params=LIST_ALL_PARAM, verify=False).json()

    # FIXME: This may break eventually..
    assert objs['total_pages'] <= 1
    return objs['objects']


_group_cache = {}
_docset_cache = {}
_grouptype_cache = {}
_doctype_cache = {}
_pubtype_cache = {}


def get_existing_types(s, api_root):
    grouptype = _get_all(s, api_root, 'group_type')
    doctype = _get_all(s, api_root, 'doc_type')
    pubtype = _get_all(s, api_root, 'pub_type')

    for r in (grouptype, doctype, pubtype):
        assert len(r) > 0

    # Build maps of existing types
    _grouptype_cache.update({x['name']: x['id'] for x in grouptype})
    _doctype_cache.update({x['name']: x['id'] for x in doctype})
    _pubtype_cache.update({x['name']: x['id'] for x in pubtype})


def fill_caches(s, api_root, groups=True, docsets=True):
    if groups:
        groups = _get_all(s, api_root, 'group')
        for g in groups:
            _group_cache[g['name']] = g
    if docsets:
        docsets = _get_all(s, api_root, 'doc_set')
        for d in docsets:
            assert d['pubtype_id'] in _pubtype_cache.values()
            assert d['doctype_id'] in _doctype_cache.values()
            _docset_cache[(d['published'], d['pubtype_id'], d['doctype_id'])] = d


def get_existing_docs(s, api_root):
    return _get_all(s, api_root, 'document')


def get_or_make_group(s, api_root, name, gtype, parent):
    if parent == name:
        # don't make circular links, it makes me sad.
        parent = None
    if gtype is not None and gtype not in _grouptype_cache:
        logging.error("Grouptype %s is not in DB!!" % (gtype,))

    # Slight hack: Maybe the parent is missing "本部" from the name?
    if parent and (parent not in _group_cache) and (parent + u'本部' in _group_cache):
        parent = parent + u'本部'

    if name in _group_cache:
        cached_group = _group_cache[name]
        if parent is not None and cached_group['parent_id'] is None:
            if parent in _group_cache:
                # update name of parent
                parentid = _group_cache[parent]['id']
                cached_group['parent_id'] = parentid
                result = s.patch(api_root + 'group/%d' % cached_group['id'],
                                 data=json.dumps({'parent_id': parentid})).json()
                assert result['parent_id']
                return cached_group
            else:
                logging.info("Update group %s parent %s unknown" % (name, parent))

        if gtype and _grouptype_cache.get(gtype) != int(cached_group['type_id']):
            logging.warn("Group %s type %s (%s) previously recorded as type %s!!" %
                         (name, gtype, _grouptype_cache.get(gtype), _group_cache[name]['type_id']))
        return cached_group

    assert(gtype is not None)

    parent_id = None
    if parent is not None:
        if parent in _group_cache:
            parent_id = _group_cache[parent]['id']
        else:
            logging.info("Update group %s parent %s unknown" % (name, parent))

    if gtype not in _grouptype_cache:
        logging.warn("Unknown group type: %s" % gtype)
        return

    obj = {'name': name, 'type_id': _grouptype_cache[gtype], 'parent_id': parent_id}
    result = s.post(api_root + 'group', data=json.dumps(obj), verify=False).json()
    if 'id' not in result:
        raise ValueError('Group add: got back %s' % result)
    _group_cache[name] = result
    return result


def get_or_make_docset(s, api_root, title, docset_type, docdir):
    docset_date = title_date(title)

    if docset_date is None:
        logging.warn(u"Couldn't guess pub date from title %s" % title)
        return

    docset_pubtype = None
    for pubtype in _pubtype_cache:
        if pubtype in title:
            docset_pubtype = _pubtype_cache[pubtype]
            break

    if docset_pubtype is None:
        logging.warn(u"Couldn't guess pubtype from title %s" % title)
        return

    if docset_type in DOCSETTYPE_MAPPING:
        docset_type = DOCSETTYPE_MAPPING[docset_type]

    if docset_type not in _doctype_cache:
        logging.warn(u"Doc type %s not in DB" % docset_type)
        # Search for similar docsets in the cache
        keys = filter(lambda x: x[0] == docset_date and x[1] == docset_pubtype, _docset_cache.keys())
        if len(keys) == 1:
            docset_type = keys[0][2]
            logging.warn(u" .. assuming type %s already in DB" % docset_type)
        else:
            return
    else:
        docset_type = _doctype_cache[docset_type]

    key = (docset_date, docset_pubtype, docset_type)
    if key in _docset_cache:
        return _docset_cache[key]

    obj = {'published': str(docset_date), 'pubtype_id': docset_pubtype, 'doctype_id': docset_type, 'path': docdir}
    result = s.post(api_root + 'doc_set', data=json.dumps(obj), verify=False).json()
    if 'id' not in result:
        raise ValueError('Docset add: got back %s' % result)
    _docset_cache[key] = result

    return result


def make_doc(s, api_root, docsetid, year, groupid, docfname, url, srcurl, fsize, pagecount, note):
    m = YEAR_RE.match(year)
    if not m:
        raise ValueError("Year %s in metadata for %s doesn't look like a year." % (year, docfname))
    year = year_to_western(*m.groups())
    obj = {'docset_id': docsetid, 'year': year, 'group_id': groupid, 'filename': docfname,
           'url': url, 'srcurl': srcurl, 'size': fsize, 'pages': pagecount, 'note': note}
    result = s.post(api_root + 'document', data=json.dumps(obj), verify=False).json()
    if 'id' not in result:
        raise ValueError('Document add: got back %s' % result)

    return result


def check_pdf(s, pdf_path, pdf_root, api_root, docs_by_url, nodefer, groupsonly):
    relative_path = pdf_path[len(pdf_root):]
    meta = metautil.get_meta(pdf_path)

    if meta is None:
        logging.warn("Skip %s which has no metadata!" % relative_path)
        return

    if 'title' not in meta or 'url' not in meta or 'srcurl' not in meta:
        logging.warn("Invalid metadata for %s!" % relative_path)
        return

    url = meta['url']
    if url in docs_by_url:
        # Verify the contents.. should be the same source
        record = docs_by_url[url]
        if record['srcurl'] != meta['srcurl']:
            logging.warn('Difference sources for %s at %s and in db: %s vs %s'
                         % (url, relative_path, record['srcurl'], meta['srcurl']))
        return
    else:
        gname = meta['srctitle']

        note = None

        notepart = MULTIPART_RE.search(gname)
        # logging.info(u"Group %s notepart %s." % (gname, notepart))
        if notepart is not None:
            notepart = notepart.groups()
            gname = notepart[0]
            note = notepart[1]

        if note:
            note = note.strip()
        gname = gname.strip()

        if 'grouptype' not in meta and gname not in _group_cache:
            if nodefer:
                logging.info(u"Recording %s as unknown." % (gname,))
                meta['grouptype'] = u'不明'
            else:
                logging.info(u"Defer %s (%s) to get more group data" % (relative_path, gname))
                return
        gtype = meta.get('grouptype')
        # Sometimes this name has a の..
        if gtype == u'政党の本部':
            gtype = u'政党本部'
        if gtype == u'政党の支部':
            gtype = u'政党支部'
        if gtype == u'総括文書（支部分）':
            gtype = u'政党支部'
        if gtype == u'資金管理団体（国会議員関係政治団体を除く。）':
            gtype = u'資金管理団体'
        if gtype == u'国会議員関係政治団体（政党の支部を除く。）':
            gtype = u'国会議員関係政治団体'
        if gtype == u'政党':
            # This could be honbu or shibu
            gtype = None

        title = meta['title']
        title_parts = title.split('\t')
        parent = None
        if len(title_parts) == 2:
            parent = title_parts[1].strip()
            if len(parent) <= 1:
                parent = None

        group = get_or_make_group(s, api_root, gname, gtype, parent)
        if group is None:
            # Something went wrong.. unknown type?
            return

        docdir, docfname = os.path.split(relative_path)
        docset = get_or_make_docset(s, api_root, title, meta['docsettype'], docdir)

        if groupsonly:
            return

        # Collect pdf stats - size and pages
        fsize = os.stat(pdf_path).st_size
        pagesre = re.compile('Pages:\s+(\d+)')
        p1 = subprocess.Popen(['pdfinfo', pdf_path], stdout=subprocess.PIPE)
        (stdoutdata, stderrdata) = p1.communicate()
        pagecount = 0
        m = pagesre.search(stdoutdata)
        if not m:
            import pdb; pdb.set_trace()
        else:
            pagecount = int(m.groups()[0])

        # finally.. make the doc.
        document = make_doc(s, api_root, docset['id'], meta['year'],
                            group['id'], docfname, meta['url'], meta['srcurl'],
                            fsize, pagecount, note)


def main():
    pdf_root_default = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'pdf')

    p = ArgumentParser(description='Import scraped documents into the database')
    p.add_argument('--pdf-root',
                   help='Root directory of PDF files to import (default: ../pdf)',
                   default=pdf_root_default)
    p.add_argument('--api-url',
                   help='Root URL of api (default: http://localhost:5000/api/raw)',
                   default='http://localhost:5000/api/raw')
    p.add_argument('--nodefer', '-n', action='store_true',
                   help='Do not defer unknown group parents and types - record as unknown')
    p.add_argument('--groupsonly', '-g', action='store_true',
                   help='Only make groups, no doc records')
    p.add_argument('--verbose', '-v', help='be more verbose',
                   action='store_true')
    p.add_argument('--quiet', '-q', help='be more quiet', action='store_true')

    args = p.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    elif args.quiet:
        logging.basicConfig(level=logging.WARN)

    if not os.path.isdir(args.pdf_root):
        p.error('pdf root is not a directory.')

    s = requests.session()
    s.headers['Content-Type'] = 'application/json'

    apiroot = args.api_url
    if not apiroot.endswith('/'):
        apiroot += '/'

    get_existing_types(s, apiroot)
    logging.info('%d group types, %d doc types, %d pub types.' %
                 (len(_grouptype_cache), len(_doctype_cache), len(_pubtype_cache)))

    fill_caches(s, apiroot)
    logging.info('%d groups, %d docsets.' %
                 (len(_group_cache), len(_docset_cache)))

    # Note: currently we don't have a huge number of docs, so just pulling all
    # the data works fine.  If this gets too slow we could pull each docset and
    # just get the count of documents in it, and compare that to the metadata
    # on-disk.  Then we could also add a --recheck option or something.
    logging.info("Getting all docs in db...")
    docs = get_existing_docs(s, apiroot)
    docs_by_url = {x['url']: x for x in docs}

    logging.info("Collecting metadata for pdfs...")
    checked = 0
    for root, dirs, files in os.walk(args.pdf_root):
        pdf_files = filter(lambda x: x.endswith('.pdf'), files)
        if not pdf_files:
            continue
        for f in pdf_files:
            pdf_file = os.path.join(root, f)
            check_pdf(s, pdf_file, args.pdf_root, apiroot, docs_by_url, args.nodefer, args.groupsonly)
            checked += 1
            if (checked % 1000) == 0:
                logging.info(".. %d pdfs checked." % checked)

    logging.info("FINISHED. %d pdfs checked." % checked)


if __name__ == '__main__':
    main()
