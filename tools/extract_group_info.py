#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import re
import logging
from argparse import ArgumentParser

from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfpage import PDFPage
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams


from cStringIO import StringIO

from toollib import metautil


sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

NAME_RE = re.compile(u'政(治(資金)?団体|党)の名称\s+(.+)')
# Note: the 'dzu' doesn't play well with REs - sometimes it's dzu, sometimes
# it's tsu+tenten.  Ignore the problem by skipping that char
type_re_str = u'政治資金規正法(及び政党助成法)?に基.く(.*)$'
TYPE_RE = re.compile(type_re_str, flags=re.UNICODE)

# One doc doesn't follow the character encoding rules, nothing can decode it
# properly.
HARDCODED_DOCS = {
    '000258038.pdf':
        {'gname': u'社会民主党',
         'doctype': u'異動の届出'}
}

TYPE_MAPPING = {
    u'政党の届出事項の異動の届出': u'異動の届出',
    u'政治団体の届出事項の異動の届出': u'異動の届出',
}

def check_pdf(pdf_dir, pdf_file):
    pdfpath = os.path.join(pdf_dir, pdf_file)
    metapath = metautil.meta_path(pdfpath)
    meta = metautil.get_meta(pdfpath)

    if meta is None:
        logging.warning('skip %s with no metadata' % pdfpath)
        return

    if meta.get('pagetype') == 'kanpo':
        # No problem, just not the type of doc we process
        return

    if meta.get('pagetype') != 'summary':
        logging.warning('skip %s with page type %s (expect summary)' % (pdfpath, meta.get('pagetype')))
        return

    if meta.get('srctitle') != u'政治資金規正法に基づく届出' or meta.get('docsettype') != u'報道資料':
        # No problem, just not the type of doc we process, or maybe already processed
        return

    pdftext = extract_pdf_text(pdfpath).decode('utf-8')

    # Some docs are really borken :(
    if pdf_file in HARDCODED_DOCS:
        gname = HARDCODED_DOCS[pdf_file]['gname']
        doctype = HARDCODED_DOCS[pdf_file]['doctype']
    elif '(cid:' in pdftext:
        logging.warning('%s contains unknown characters' % pdf_file)
        return
    else:
        lines = pdftext.splitlines()
        lines = [x.strip() for x in lines]
        gname = group_name(lines, pdf_file)
        if gname is None:
            logging.info('Couldn\'t decide a group for %s' % pdf_file)
            return
        doctype = todoke_type(lines, pdf_file)
        if doctype is None:
            logging.info('Couldn\'t decide a doctype for %s' % pdf_file)
            return
    assert gname is not None and doctype is not None
    update_meta(metapath, meta, gname, doctype)


def update_meta(metapath, meta, gname, doctype):
    meta['docsettype'] = doctype
    meta['srctitle'] = gname

    metaout = open(metapath, 'wb')
    for k, v in meta.iteritems():
        encoded_v = v
        if type(v) == unicode:
            encoded_v = v.encode('utf-8')
        metaout.write('%s,%s\n' % (str(k), str(encoded_v)))
    metaout.close()


def todoke_type(lines, pdf_file):
    ttype = None
    for i in range(len(lines)):
        l = lines[i]
        m = TYPE_RE.search(l)
        if m is None:
            continue
        ttype = m.groups()[1].strip()
        if len(lines[i+1]):
            ttype += lines[i+1]
        logging.info(u'%s doctype is %s' % (pdf_file, ttype))
        break

    return ttype


def group_name(lines, pdf_file):
    """
    Extract the best group name.  Docs can mention both a party and a funding
    group name.  The group name is what we really want, so prioritise that.
    """
    gname = None
    gtype = None
    for l in lines:
        m = NAME_RE.search(l)
        if m is None:
            continue
        if gname is not None:
            logging.warning('skip %s: 2 groups in one doc: %s [%s] and %s [%s]' % (pdf_file, gname, gtype, m.groups()[2], m.groups()[0]))
            return
        gname = m.groups()[2].strip()
        gtype = m.groups()[0].strip()
        if u'五十音順' in gname:
            # HACK: some docs are really borked..
            return
        logging.info(u'%s is a doc for %s' % (pdf_file, gname))
    return gname


LAPARAMS = LAParams()
LAPARAMS.line_margin = 10.0


def extract_pdf_text(fname):
    rsrcmgr = PDFResourceManager(caching=True)
    codec = 'utf-8'
    outfp = StringIO()
    device = TextConverter(rsrcmgr, outfp, codec=codec, laparams=LAPARAMS,
                           imagewriter=None)
    fp = file(fname, 'rb')
    interpreter = PDFPageInterpreter(rsrcmgr, device)
    for page in PDFPage.get_pages(fp, set(), maxpages=1,
                                  caching=True, check_extractable=True):
        interpreter.process_page(page)
    fp.close()
    device.close()
    return outfp.getvalue()


def main():
    pdf_root_default = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'pdf', 'main_content')

    p = ArgumentParser(description='Import scraped documents into the database')
    p.add_argument('--pdf-root',
                   help='Root directory of PDF files to examine (default: ../pdf/main_content)',
                   default=pdf_root_default)
    p.add_argument('--verbose', '-v', help='be more verbose',
                   action='store_true')
    p.add_argument('--quiet', '-q', help='be more quiet', action='store_true')
    p.add_argument('pattern', nargs='*', help='filename pattern')

    args = p.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    elif args.quiet:
        logging.basicConfig(level=logging.WARN)

    if not os.path.isdir(args.pdf_root):
        p.error('pdf root is not a directory.')

    logging.info("Extracting group names from summary notifications...")
    checked = 0

    pdf_dir = os.path.abspath(args.pdf_root)

    pdffiles = os.listdir(pdf_dir)
    pdffiles = filter(lambda x: x.endswith('.pdf'), pdffiles)
    if args.pattern:
        matches = set()
        for p in args.pattern:
            matches.update(filter(lambda x: p in x, pdffiles))
        pdffiles = list(matches)
    for f in pdffiles:
        check_pdf(pdf_dir, f)
        checked += 1
        if (checked % 1000) == 0:
            logging.info(".. %d pdfs checked." % checked)

    logging.info("FINISHED. %d pdfs checked." % checked)


if __name__ == '__main__':
    main()
