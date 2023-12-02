#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import logging
import os
from hashlib import md5
import re
import urllib.parse
import datetime
from io import BytesIO
from lxml import etree

from toollib import metautil, get_nenbun

SITE = 'https://www.soumu.go.jp'

_BLOCK_SIZE = 4096


# Remember URLs we have seen so that we only check each page once
_seen = set()

_downloaded = 0

# Hacky globals so i can reprocess metadata
_nowrite = False
_redo_meta = False


html_cache_dir = None
pdf_cache_dir = None


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
    except Exception:
        import pdb
        pdb.set_trace()

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
        url = urllib.parse.urljoin(base, url)
    return url


onclick_re = re.compile("window.open\('([^']*\.pdf)','pdf','[^']*'\);")


def parse_page(data):
    """
    Extract URLs and their names from some text.  Returns the encoding of
    the document as well, thanks to scope creep.
    """
    parser = etree.HTMLParser()
    tree = etree.parse(BytesIO(data), parser)
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


def cache_page(session, url, srcurl):
    """ Get a page with caching """
    url = normalise(url, srcurl)
    if url in _seen:
        logging.warning("ALREADY SEEN PAGE %s" % url)
        return None
    key = md5(bytes(url, "utf-8")).hexdigest()
    path = os.path.join(html_cache_dir, key)
    if not os.path.exists(path):
        save(session, url, path)
    _seen.add(url)
    return open(path, 'rb').read()


def cache_pdf(session, url, srcurl, site_base_url, ptype, title, srctitle, grouptype, year, docsettype, more_meta=None):
    """
    Get a PDF with caching.
    more_meta is an optional list of additional metadata k,v pairs
    """
    url = normalise(url, srcurl)
    if url in _seen:
        logging.warning("ALREADY SEEN PDF %s" % url)
        return

    pdf_cache_file = url[len(site_base_url):]
    if pdf_cache_file.startswith('/'):
        pdf_cache_file = pdf_cache_file[1:]
    pdf_cache_file = os.path.join(pdf_cache_dir, pdf_cache_file)
    pdf_dir = os.path.dirname(pdf_cache_file)
    if not os.path.isdir(pdf_dir):
        os.makedirs(pdf_dir)
    meta_file = metautil.meta_path(pdf_cache_file)

    if (not _redo_meta) and os.path.exists(pdf_cache_file) and os.path.exists(meta_file):
        logging.debug("already have pdf and meta for %s" % url)
        return

    try:
        meta = None
        if os.path.exists(pdf_cache_file):
            logging.warning("not overwriting pdf for %s, refreshing meta only" % url)
        elif not _redo_meta:
            save(session, url, pdf_cache_file)
        if _redo_meta and os.path.exists(meta_file):
            # For debugging..
            # oldmeta = open(meta_file, 'rb').read()
            pass

        meta = open(meta_file, 'w', encoding="utf-8")
        meta.write('url,%s\n' % url)
        meta.write('srcurl,%s\n' % srcurl)
        meta.write('title,%s\n' % title)
        meta.write('srctitle,%s\n' % srctitle)
        meta.write('pagetype,%s\n' % ptype)
        meta.write('grouptype,%s\n' % grouptype if grouptype else '')
        meta.write('docsettype,%s\n' % docsettype)
        meta.write('year,%s\n' % year)
        meta.write('fetched,%s\n' % str(datetime.datetime.now()))
        if more_meta is not None:
            for k, v in more_meta:
                meta.write('%s,%s\n' % (k, v))

        meta.close()
    except:
        if meta:
            meta.close()
            os.unlink(meta_file)
        raise


def report_url_filter(baseurl):
    def filterfn(s):
        return '?' not in s[0] and (
            ('/reports/' in s[0] or
             ('/reports/' in baseurl and '/' not in s[0] and s[0].endswith('html')))
            or
            ('/contents/' in s[0] or
             ('/contents/' in baseurl and '/' not in s[0] and s[0].endswith('pdf')))
        )
    return filterfn


def summary_url_filter(baseurl):
    def filterfn(s):
        return '?' not in s[0] and (
            ('/kanpo/' in s[0] or
             ('/kanpo/' in baseurl and '/' not in s[0] and s[0].endswith('html')))
            or
            ('/main_content/' in s[0] or
             ('/main_content/' in baseurl and '/' not in s[0] and s[0].endswith('pdf')))
        )
    return filterfn


def page_auto(session, url, base_url, ptype, title, srcurl, data=None, grouptype=None, year=None):
    """
    Work out if this page is a table with a bunch of different sub-pages, or a simple list of PDFs
    """
    logging.debug('%s: %s, %s' % (ptype, title, url))
    data = data or cache_page(session, url, base_url)
    if data is None:
        return
    # Massive HACK (2023-12-02) this page:
    # https://www.soumu.go.jp/senkyo/seiji_s/seijishikin/reports/SS20221125/SS/11.html
    # is broken, it as a 0 at the front which causes the parser to fail, and also has
    # massive weird null characters
    if data[0:2] == b'0<':
        data = data[1:]
        data = data.replace(b'\0', b'')
    urls, encoding, pagetitle = parse_page(data)
    repurls = list(filter(report_url_filter(url), urls))

    if not len(repurls):
        import pdb; pdb.set_trace()
        logging.debug(' (no good urls)')
        return

    node = repurls[0][2]
    td = node.getparent()
    if td.tag == 'td':
        logging.debug('.... has children')
        _page_with_children(session, url, title, ptype, base_url, data, repurls, encoding, pagetitle, _grouptype=grouptype, _year=year)
    else:
        logging.debug('.... is a pdf list')
        _pdf_list_page(session, url, base_url, ptype, title, srcurl, data, repurls, encoding, pagetitle, _grouptype=grouptype, _year=year)


def _pdf_list_page(session, url, site_base_url, ptype, title, srcurl, data, repurls, encoding, pagetitle, _grouptype=None, _year=None):
    """ Process a page which is just links to a bunch of PDFs """
    pdfurls = [u for u in repurls if u[0].endswith('.pdf')]
    for purl, ptitle, node in pdfurls:
        if ptitle is None:
            # HACK: Hand code a couple of broken corner cases
            if purl.endswith('SD20110228/220210.pdf') or purl.endswith('SA20110228/200210.pdf'):
                ptitle = '高健社'
            else:
                logging.warning('No title for %s..' % purl)
                ptitle = '(無題)'

        # Find the group type and year for non teiki pages
        grouptype = _grouptype
        year = _year
        if grouptype is None:
            assert year is None
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
                import pdb
                pdb.set_trace()
            year = get_nenbun(previous.text)

        cache_pdf(session, purl, url, site_base_url, ptype, title, ptitle, grouptype, year, pagetitle)


# Processor functions all take the same arguments:
def _page_with_children(session, url, title, ptype, base_url, data, repurls, encoding, pagetitle, _grouptype=None, _year=None):
    """ Process data that is split into sub-pages. """
    year = _year or get_nenbun(title)

    grouptypes = None
    grouptype_tb = None

    for suburl, linktitle, node in repurls:
        td = node.getparent()
        assert td.tag == 'td'
        tr = td.getparent()
        assert tr.tag == 'tr'
        tb = tr.getparent()
        assert tb.tag == 'table'

        if tb.attrib.get('id').startswith('list-item'):
            # embedded table..
            td = tb.getparent()
            assert td.tag == 'td'
            tr = td.getparent()
            assert tr.tag == 'tr'
            tb = tr.getparent()
            assert tb.tag == 'table'

        if grouptypes is None or tb != grouptype_tb:
            types = tb.xpath('./tr/th')
            grouptypes = [''.join(x.itertext()).strip() for x in types]
            grouptype_tb = tb

        colno = tr.xpath('./td').index(td)

        if not (colno < len(grouptypes) or _grouptype is not None):
            import pdb; pdb.set_trace()

        if colno < len(grouptypes):
            grouptype = grouptypes[colno]

            # Horrible hack method to check title, works on some pages..
            sdata = data.decode(encoding)
            grouptype_offset = sdata.rfind('<!--', 0, sdata.index(suburl)) + 5
            grouptype_comment = sdata[grouptype_offset:grouptype_offset+20]
            grouptype_b = grouptype_comment.split()[0]
            if grouptype_b == '議員別' and grouptype.startswith('国会議員関係政治団体'):
                grouptype = grouptype_b
            elif grouptype_b == '政党支部':
                # Hack for http://www.soumu.go.jp/senkyo/seiji_s/seijishikin/reports/SS20181130/
                # which drops the "no" in the comment
                grouptype_b = '政党の支部'
            elif grouptype_b.startswith('<'):
                # Nope, not what we were looking for.
                grouptype_b = None

            if not (not grouptype_b or grouptype_b == 'タイトル終了' or grouptype_b == grouptype):
                logging.error('ERROR: Group type in comment (%s) dosn\'t match group type in table heading!! (%s)' % grouptype_b, grouptype)
                logging.error('URL: %s' % url)
                logging.error('breaking into the debugger so you can sort it out :(')
                import pdb; pdb.set_trace()

            assert (_grouptype is None) or (grouptype == _grouptype)
        else:
            grouptype = _grouptype

        suburl = normalise(suburl, url)
        logging.debug('   %s, %s %s' % (suburl, linktitle, grouptype))
        if suburl.endswith('.pdf'):
            cache_pdf(session, suburl, url, base_url, ptype, title, linktitle, grouptype, year, pagetitle)
        else:
            combined_title = '%s\t%s' % (title, linktitle)
            sub_ptype = ptype + 'sub'
            page_auto(session, suburl, base_url, sub_ptype, combined_title, url, data=None, grouptype=grouptype, year=year)


def kaisan(session, url, title, base_url):
    """ Process end of term data. Just a bunch of PDFs """
    page_auto(session, url, base_url, 'kaisan', title, base_url)


def kaisanshibu(session, url, title, base_url):
    """ Process end of term branch data. Links to a bunch of sub-pages """
    page_auto(session, url, base_url, 'kaisanshibu', title, base_url)


def tsuika(session, url, title, base_url):
    """ Process additional data.  Also just a bunch of PDFs """
    page_auto(session, url, base_url, 'tsuika', title, base_url)


def teiki(session, url, title, base_url):
    """ Process additional data.  Also just a bunch of PDFs """
    page_auto(session, url, base_url, 'teiki', title, base_url)


def kanpo(session, url, title, base_url):
    """ 官報 data - page of pdf links with hash-parts and a different format"""
    logging.debug('%s: %s, %s' % ('kanpo', title, url))
    data = cache_page(session, url, base_url)
    if data is None:
        return
    urls, encoding, pagetitle = parse_page(data)
    urls = list(filter(summary_url_filter(url), urls))

    linkdata = {}

    for href, text, node in urls:
        if '#' in href:
            href, hashpart = href.split('#')
            assert hashpart.startswith('page=')
            pageno = int(hashpart[5:])
        else:
            pageno = 1
        link = '%s\t%d' % (text, pageno)
        if href in linkdata:
            linkdata[href].append(('page', link))
        else:
            linkdata[href] = [('page', link)]

    ptype = 'kanpo'
    srctitle = '政治資金収支報告書の要旨'
    grouptype = None
    year = get_nenbun(title)
    docsettype = '官報'
    title = title + ' (官報)'

    for href, links in linkdata.items():
        cache_pdf(session, href, base_url, SITE, ptype, title, srctitle, grouptype, year, docsettype, more_meta=links)


def summary_pdf_downloader(session, href, text, base_url, node):
    """
    the summary page has a few different pdfs linked directly from it:
    総務大臣届出分 - a breakdown of all the numbers
    総務大臣届出分＋都道府県選管届出分 - breakdown of numbers including regional (summary only)
    政治資金規正法に基づく届出 - notices of group formation/dissolution etc
    """
    assert href.endswith('.pdf')
    dd = node.getparent()
    if dd.tag != 'dd':
        import pdb; pdb.set_trace()
    assert dd.tag == 'dd'
    dl = dd.getparent()
    assert dl.tag == 'dl'
    head = dl.getprevious()
    assert head.tag == 'h5'
    while dd is not None and dd.tag == 'dd':
        dd = dd.getprevious()
    if dd is not None and dd.tag == 'dt':
        assert head.text.startswith('政治資金収支報告の概要')
        #docsettype = u'政治資金収支報告の概要'
        srctitle = dd.text[1:-1]
    else:
        assert head.text.startswith('政治資金規正法に基づく届出')
        srctitle = '政治資金規正法に基づく届出'

    docsettype = '報道資料'

    title = text + ' (報道資料)'
    ptype = 'summary'
    grouptype = None
    year = get_nenbun(text, weak=True)

    cache_pdf(session, href, base_url, SITE, ptype, title, srctitle, grouptype, year, docsettype)


# There are three types of page, each with their own processor function
processors = {'定期公表': teiki,
              '解散分': kaisan,
              '解散支部分': kaisanshibu,
              '追加分': tsuika,
              '日付け官報': kanpo}


def check_dir(data_dir, create=False):
    if not os.path.isdir(data_dir):
        if create:
            logging.info("Creating new directory: %s" % data_dir)
            os.mkdir(data_dir)
        else:
            raise Exception("Data dir %s doesn't exist - use --mkdirs to create it." % data_dir)


def scrape_from(base_url, pattern, is_summary):
    logging.info("Starting at %s" % base_url)
    session = requests.Session()

    today = str(datetime.date.today())
    cache_key = [x for x in base_url.split('/') if x][-1] + '-' + today
    path = os.path.join(html_cache_dir, cache_key)
    if not os.path.exists(path):
        save(session, base_url, path)
    _seen.add(base_url)
    data = open(path, 'rb').read()
    # data = open('test.html').read()

    urls, encoding, pagetitle = parse_page(data)

    if is_summary:
        filter_fn = summary_url_filter(base_url)
    else:
        filter_fn = report_url_filter(base_url)

    urls = list(filter(filter_fn, urls))
    logging.debug("%d starting urls" % len(urls))
    for href, text, node in urls:
        if pattern and not any([p in href for p in pattern]):
            continue
        href = normalise(href, base_url)
        for k, p in list(processors.items()):
            if k in text:
                p(session, href, text, base_url)
        if is_summary and href.endswith('.pdf'):
            # Sepecial case for the junk linked off the main summary page..
            #summary_pdf_downloader(session, href, text, base_url, node)
            continue


def recheck_meta(base_url):
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
    for root, dirs, files in os.walk(pdf_cache_dir):
        meta_files = list(filter(metautil.is_meta_path, files))
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
            title = meta['title']

            # So many hacks :(
            if ptype == 'teikisub':
                srcurl = meta['srcurl']
                if srcurl.startswith('http'):
                    srcurl = srcurl[len(SITE):]
                match = [x for x in list(cache_data.values()) if '"%s"' % srcurl in x]
                if len(match) != 1:
                    import pdb
                    pdb.set_trace()
                    raise
                # FIXME: this is broken
                _page_with_children(FakeSession(), htmlurl, title.split('\t')[0], 'teiki', base_url, data=match[0])
            else:
                # FIXME: this is broken too
                _pdf_list_page(FakeSession(), htmlurl, base_url, ptype, title, base_url)

            processed_pages.add(htmlurl)


def main():
    tooldir = os.path.dirname(os.path.abspath(__file__))

    CACHE_DIR = os.path.abspath(os.path.join(tooldir, '..', 'cache'))
    PDF_DIR = os.path.abspath(os.path.join(tooldir, '..', 'pdf'))

    BASE_URL = SITE + '/senkyo/seiji_s/seijishikin/'
    BASE_URL_DATA = SITE + '/senkyo/seiji_s/data_seiji/'

    from argparse import ArgumentParser

    p = ArgumentParser(description="Script to scrape contribution data from 総務省.")
    p.add_argument("--pdfdir", "-p", help="PDF file cache path", default=PDF_DIR)
    p.add_argument("--cachedir", "-c", help="html file cache path", default=CACHE_DIR)
    p.add_argument("--mkdirs", "-m", action="store_true", help="create cache and pdf dir if they don't exist")
    p.add_argument("--verbose", "-v", action="store_true", help="be more verbose")
    p.add_argument("--recheck-meta", "-r", action="store_true", help="recheck metadata by reparsing html")
    p.add_argument("--data-only", "-d", action="store_true", help="only check the 'data' page")
    p.add_argument('pattern', nargs='*', help='page pattern')

    args = p.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    for data_dir in (args.cachedir, args.pdfdir):
        check_dir(data_dir, create=args.mkdirs)

    logging.debug("HTML cache is %s" % args.cachedir)
    global html_cache_dir
    html_cache_dir = args.cachedir

    logging.debug("PDF cache is %s" % args.pdfdir)
    global pdf_cache_dir
    pdf_cache_dir = args.pdfdir

    if not args.recheck_meta:
        if not args.data_only:
            scrape_from(BASE_URL, args.pattern, False)
        scrape_from(BASE_URL_DATA, args.pattern, True)
        logging.debug("Downloaded %d files." % _downloaded)
    else:
        recheck_meta(BASE_URL)

if __name__ == '__main__':
    main()
