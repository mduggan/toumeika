#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import logging
import os
import md5
import re
import urlparse
from cStringIO import StringIO
from lxml import etree

SITE = 'http://www.soumu.go.jp'

_BLOCK_SIZE = 4096


# Remember URLs we have seen so that we only check each page once
_seen = set()

_downloaded = 0

NENBUN = re.compile(u'((平成|昭和)\d+)年分')

# Hacky globals so i can reprocess metadata
_nowrite = False
_redo_meta = False


def save(session, url, path):
    global _downloaded
    logging.debug('save url %s -> %s' % (url, path))
    r = session.get(url)
    if r.status_code != 200:
        raise Exception('%d fetching %s' % (r.status_code, url))
    try:
        if _nowrite:
            logging.debug("not writing %s because of _nowrite global" % path)
            return
        with open(path, 'wb') as fd:
            for chunk in r.iter_content(4096):
                fd.write(chunk)
    except Exception, e:
        import pdb; pdb.set_trace()

        os.unlink(path)
        raise
    _downloaded += 1


def normalise(url, base):
    """
    Normalise the given url against a local base.  Also makes sure that the
    overall site base is part of the URL.
    """
    assert(base is None or base.startswith('http'))
    if url.startswith('http'):
        return url

    if base:
        url = urlparse.urljoin(base, url)
    return url


onclick_re = re.compile("window.open\('([^']*\.pdf)','pdf','[^']*'\);")


def parse_page(text):
    """
    Extract URLs and their names from some text.  Returns the encoding of
    the document as well, thanks to scope creep.
    """
    parser = etree.HTMLParser()
    tree = etree.parse(StringIO(text), parser)
    urls = []
    links = tree.xpath('//a')
    for l in links:
        if 'href' not in l.attrib:
            continue
        href = l.attrib['href']
        if href.startswith('#') or href == '/':
            if 'onclick' in l.attrib:
                match = onclick_re.match(l.attrib['onclick'])
                if match:
                    href = match.groups()[0]
                else:
                    continue
            else:
                # Ignore pointless links..
                continue
        urls.append((href, l.text, l))
    title = tree.xpath('//*[@id="title"]')
    if len(title):
        title = title[0].text.strip()
    else:
        title = None
    return urls, tree.docinfo.encoding, title


def cache_page(session, url, srcurl, html_cache_dir):
    """ Get a page with caching """
    url = normalise(url, srcurl)
    if url in _seen:
        logging.warn("ALREADY SEEN PAGE %s" % url)
        return None
    key = md5.md5(url).hexdigest()
    path = os.path.join(html_cache_dir, key)
    if not os.path.exists(path):
        save(session, url, path)
    _seen.add(url)
    return open(path).read()


def cache_pdf(session, url, srcurl, site_base_url, ptype, title, srctitle, pdf_dir, grouptype, year, docsettype):
    """ Get a PDF with caching """
    url = normalise(url, srcurl)
    if url in _seen:
        logging.warn("ALREADY SEEN PDF %s" % url)
        return

    pdf_cache_file = url[len(site_base_url):]
    pdf_cache_file = os.path.join(pdf_dir, pdf_cache_file)
    pdf_cache_dir = os.path.dirname(pdf_cache_file)
    if not os.path.isdir(pdf_cache_dir):
        os.makedirs(pdf_cache_dir)
    meta_file = pdf_cache_file + '_meta.txt'

    if (not _redo_meta) and os.path.exists(pdf_cache_file) and os.path.exists(meta_file):
        logging.debug("already have pdf and meta for %s" % url)
        return

    try:
        if not _redo_meta:
            save(session, url, pdf_cache_file)
        if _redo_meta and os.path.exists(meta_file):
            # For debugging..
            # oldmeta = open(meta_file, 'rb').read()
            pass

        meta = open(meta_file, 'wb')
        meta.write('url,%s\n' % url)
        meta.write('srcurl,%s\n' % srcurl)
        meta.write('title,%s\n' % title.encode('utf-8'))
        meta.write('srctitle,%s\n' % srctitle.encode('utf-8'))
        meta.write('pagetype,%s\n' % ptype.encode('utf-8'))
        meta.write('grouptype,%s\n' % grouptype.encode('utf-8') if grouptype else '')
        meta.write('docsettype,%s\n' % docsettype.encode('utf-8'))
        meta.write('year,%s\n' % year.encode('utf-8'))
        meta.close()
    except:
        meta.close()
        os.unlink(meta_file)
        raise


def report_url_filter(baseurl):
    def filterfn(s):
        return '?' not in s[0] and ('/reports/' in s[0] or
                                    ('/reports/' in baseurl and '/' not in s[0] and s[0].endswith('html')))
    return filterfn


def get_nenbun(text):
    year = NENBUN.search(text)
    if year is not None:
        year = year.groups()[0]
    return year


def pdf_page(session, url, site_base_url, ptype, title, srcurl, cache_dir, pdf_dir, _grouptype=None, _year=None):
    logging.debug('%s: %s, %s' % (ptype, title, url))
    data = cache_page(session, url, srcurl, cache_dir)
    if data is None:
        return
    urls, encoding, pagetitle = parse_page(data)
    pdfurls = filter(lambda u: u[0].endswith('.pdf'), urls)
    for purl, ptitle, node in pdfurls:
        if ptitle is None:
            # HACK: Hand code a couple of broken corner cases
            if purl.endswith('SD20110228/220210.pdf') or purl.endswith('SA20110228/200210.pdf'):
                ptitle = u'高健社'
            else:
                logging.warn('No title for %s..' % purl)
                ptitle = u'(無題)'
        # Kinda hacky.. find the group type and year for non teiki pages
        grouptype = _grouptype
        year = _year
        if grouptype is None:
            previous = node.getprevious()
            while previous is not None and previous.tag != 'strong':
                previous = previous.getprevious()
            # Group types aren't always in kaisan..
            if previous is not None:
                grouptype = previous.text.strip('[]')
            previous = node.getparent()
            if previous is not None and previous.tag != 'div':
                previous = previous.getparent()
            while previous is not None and previous.tag != 'span':
                previous = previous.getprevious()
            if previous is None:
                # No pages like this yet
                import pdb; pdb.set_trace()
            year = get_nenbun(previous.text)

        cache_pdf(session, purl, url, site_base_url, ptype, title, ptitle, pdf_dir, grouptype, year, pagetitle)


# Processor functions all take the same arguments:
def teiki(session, url, title, base_url, cache_dir, pdf_dir, data=None):
    """ Process regular data - this is split into sub-pages. """
    logging.debug('teiki: %s, %s' % (title, url))
    data = data or cache_page(session, url, base_url, cache_dir)
    if data is None:
        return
    urls, encoding, pagetitle = parse_page(data)
    repurls = filter(report_url_filter(url), urls)
    year = get_nenbun(title)

    grouptypes = None

    for suburl, subtitle, node in repurls:
        td = node.getparent()
        tr = td.getparent()
        if grouptypes is None:
            tb = tr.getparent()
            types = tb.xpath('//th')
            grouptypes = [''.join(x.itertext()).strip() for x in types]
        colno = tr.index(td)
        grouptype = grouptypes[colno]

        # TODO: Horrible hack, but search back to find the title of this seciton..
        grouptype_offset = data.rfind('<!--', 0, data.index(suburl)) + 5
        grouptype_b = data[grouptype_offset:grouptype_offset+20].decode(encoding).split()[0]

        if grouptype_b and grouptype_b != u'タイトル終了' and grouptype_b != grouptype:
            import pdb; pdb.set_trace()

        suburl = normalise(suburl, url)
        logging.debug('   %s, %s %s' % (suburl, subtitle, grouptype))
        pdf_page(session, suburl, base_url, 'teikisub', u'%s\t%s' % (title, subtitle), url, cache_dir, pdf_dir, _grouptype=grouptype, _year=year)


def kaisan(session, url, title, base_url, cache_dir, pdf_dir):
    """ Process end of term data. Just a bunch of PDFs """
    pdf_page(session, url, base_url, 'kaisan', title, base_url, cache_dir, pdf_dir)


def kaisanshibu(session, url, title, base_url, cache_dir, pdf_dir):
    """ Process end of term branch data. Links to a bunch of sub-pages """
    logging.warn("Write me: 解散支部分")
    pdf_page(session, url, base_url, 'kaisanshibu', title, base_url, cache_dir, pdf_dir)


def tsuika(session, url, title, base_url, cache_dir, pdf_dir):
    """ Process additional data.  Also just a bunch of PDFs """
    pdf_page(session, url, base_url, 'tsuika', title, base_url, cache_dir, pdf_dir)


# There are three types of page, each with their own processor function
processors = {u'定期公表': teiki,
              u'解散分': kaisan,
              u'解散支部分': kaisanshibu,
              u'追加分': tsuika}


def check_dir(data_dir, create=False):
    if not os.path.isdir(data_dir):
        if create:
            logging.info("Creating new directory: %s" % data_dir)
            os.mkdir(data_dir)
        else:
            raise Exception("Data dir %s doesn't exist - use --mkdirs to create it." % data_dir)


def scrape_from(base_url, html_cache_dir, pdf_dir, pattern):
    logging.info("Starting at %s" % base_url)
    session = requests.Session()

    data = session.get(base_url).content
    # data = open('test.html').read()
    urls, encoding, pagetitle = parse_page(data)
    urls = filter(report_url_filter(base_url), urls)
    for href, text, node in urls:
        if pattern and not any([p in href for p in pattern]):
            continue
        href = normalise(href, base_url)
        for k, p in processors.items():
            if k in text:
                p(session, href, text, base_url, html_cache_dir, pdf_dir)


def recheck_meta(base_url, html_cache_dir, pdf_dir):
    global _redo_meta
    global _nowrite
    _redo_meta = True
    _nowrite = True
    class FakeSession():
        pass

    processed_pages = set()

    logging.info("reading all cached html files..")
    cache_data = {}
    cache_files = os.listdir(html_cache_dir)
    for f in cache_files:
        cache_data[f] = open(os.path.join(html_cache_dir, f), 'rb').read()

    logging.info("checking cached pdf files..")
    for root, dirs, files in os.walk(pdf_dir):
        meta_files = filter(lambda x: x.endswith('_meta.txt'), files)
        if not meta_files:
            continue
        for metafile in meta_files:
            metapath = os.path.join(root, metafile)
            meta = dict([x.strip().split(',') for x in open(metapath).readlines()])
            htmlurl = meta['srcurl']
            htmlurl = normalise(htmlurl, base_url)
            if htmlurl in processed_pages:
                continue
            srctitle = meta['srctitle']
            ptype = meta['pagetype']
            title = meta['title'].decode('utf-8')

            # So many hacks :(
            if ptype == 'teikisub':
                srcurl = meta['srcurl']
                if srcurl.startswith('http'):
                    srcurl = srcurl[len(SITE):]
                match = filter(lambda x: '"%s"' % srcurl in x, cache_data.values())
                if len(match) != 1:
                    import pdb; pdb.set_trace()
                    raise
                teiki(FakeSession(), htmlurl, title.split(u'\t')[0], base_url, html_cache_dir, pdf_dir, data=match[0])
            else:
                pdf_page(FakeSession(), htmlurl, base_url, ptype, title, base_url, html_cache_dir, pdf_dir)

            processed_pages.add(htmlurl)


def main():
    tooldir = os.path.dirname(os.path.abspath(__file__))

    CACHE_DIR = os.path.abspath(os.path.join(tooldir, '..', 'cache'))
    PDF_DIR = os.path.abspath(os.path.join(tooldir, '..', 'pdf'))

    BASE_URL = SITE + '/senkyo/seiji_s/seijishikin/'

    from argparse import ArgumentParser

    p = ArgumentParser(description="Script to scrape contribution data from 総務省.")
    p.add_argument("--pdfdir", "-p", help="PDF file cache path", default=PDF_DIR)
    p.add_argument("--cachedir", "-c", help="html file cache path", default=CACHE_DIR)
    p.add_argument("--mkdirs", "-m", action="store_true", help="create cache and pdf dir if they don't exist")
    p.add_argument("--verbose", "-v", action="store_true", help="be more verbose")
    p.add_argument("--recheck-meta", "-r", action="store_true", help="recheck metadata by reparsing html")
    p.add_argument('pattern', nargs='*', help='page pattern')

    args = p.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    for data_dir in (args.cachedir, args.pdfdir):
        check_dir(data_dir, create=args.mkdirs)

    logging.debug("HTML cache is %s" % args.cachedir)
    logging.debug("PDF cache is %s" % args.pdfdir)

    if not args.recheck_meta:
        scrape_from(BASE_URL, args.cachedir, args.pdfdir, args.pattern)
        logging.debug("Downloaded %d files." % _downloaded)
    else:
        recheck_meta(BASE_URL, args.cachedir, args.pdfdir)

if __name__ == '__main__':
    main()
