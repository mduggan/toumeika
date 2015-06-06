#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import logging
import os
import md5
import urlparse
from cStringIO import StringIO
from lxml import etree

_BLOCK_SIZE = 4096


# Remember URLs we have seen so that we only check each page once
_seen = set()

_downloaded = 0


def save(session, url, path):
    global _downloaded
    logging.debug('save url %s -> %s' % (url, path))
    r = session.get(url)
    if r.status_code != 200:
        raise Exception('%d fetching %s' % (r.status_code, url))
    try:
        with open(path, 'wb') as fd:
            for chunk in r.iter_content(4096):
                fd.write(chunk)
    except:
        os.unlink(path)
        raise
    _downloaded += 1


def normalise(url, base):
    """
    Normalise the given url against a local base.  Also makes sure that the
    overall site base is part of the URL.
    """
    assert(base is None or base.startswith('http'))
    if base:
        url = urlparse.urljoin(base, url)
    return url


def get_urls(text):
    """ Extract URLs and their names from some text """
    parser = etree.HTMLParser()
    tree = etree.parse(StringIO(text), parser)
    urls = []
    links = tree.xpath('//a')
    for l in links:
        attrs = dict(l.items())
        if 'href' not in attrs:
            continue
        href = attrs['href']
        urls.append((href, l.text))
    return urls


def cache_page(session, url, srcurl, html_cache_dir):
    """ Get a page with caching """
    url = normalise(url, srcurl)
    if url in _seen:
        logging.warn("ALREADY SEEN %s" % url)
        return
    key = md5.md5(url).hexdigest()
    path = os.path.join(html_cache_dir, key)
    if not os.path.exists(path):
        save(session, url, path)
    _seen.add(url)
    return open(path).read()


def cache_pdf(session, url, srcurl, site_base_url, ptype, title, srctitle, pdf_dir):
    """ Get a PDF with caching """
    url = normalise(url, srcurl)
    if url in _seen:
        logging.warn("ALREADY SEEN %s" % url)
        return

    pdf_cache_file = url[len(site_base_url):]
    pdf_cache_file = os.path.join(pdf_dir, pdf_cache_file)
    pdf_cache_dir = os.path.dirname(pdf_cache_file)
    if not os.path.isdir(pdf_cache_dir):
        os.makedirs(pdf_cache_dir)
    meta_file = pdf_cache_file + '_meta.txt'

    if os.path.exists(pdf_cache_file) and os.path.exists(meta_file):
        logging.debug("already have pdf and meta for %s" % url)
        return

    meta = open(meta_file, 'wb')
    try:
        save(session, url, pdf_cache_file)
        meta.write('url,%s\n' % url)
        meta.write('srcurl,%s\n' % srcurl)
        meta.write('title,%s\n' % title.encode('utf-8'))
        meta.write('srctitle,%s\n' % srctitle.encode('utf-8'))
        meta.write('pagetype,%s\n' % ptype.encode('utf-8'))
        meta.close()
    except:
        meta.close()
        os.unlink(meta_file)
        raise


def report_url_filter(s):
    return '?' not in s[0] and 'reports/S' in s[0]


def pdf_page(session, url, site_base_url, ptype, title, srcurl, cache_dir, pdf_dir):
    logging.debug('%s: %s, %s' % (ptype, title, url))
    data = cache_page(session, url, srcurl, cache_dir)
    urls = get_urls(data)
    pdfurls = filter(lambda u: u[0].endswith('.pdf'), urls)
    for purl, ptitle in pdfurls:
        if ptitle is None:
            logging.warn('Invalid title for %s..' % purl)
            ptitle = '__INVALID__'
            continue
        cache_pdf(session, purl, url, site_base_url, ptype, title, ptitle, pdf_dir)


# Processor functions all take the same arguments:
def teiki(session, url, title, base_url, cache_dir, pdf_dir):
    """ Process regular data - this is split into sub-pages. """
    logging.debug('teiki: %s, %s' % (title, url))
    data = cache_page(session, url, base_url, cache_dir)
    urls = get_urls(data)
    repurls = filter(report_url_filter, urls)
    for suburl, subtitle in repurls:
        suburl = normalise(suburl, url)
        logging.debug('   %s, %s' % (suburl, subtitle))
        pdf_page(session, suburl, base_url, 'teikisub', '%s\t%s' % (title, subtitle), url, cache_dir, pdf_dir)


def kaisan(session, url, title, base_url, cache_dir, pdf_dir):
    """ Process end of term data. Just a bunch of PDFs """
    pdf_page(session, url, base_url, 'kaisan', title, base_url, cache_dir, pdf_dir)


def tsuika(session, url, title, base_url, cache_dir, pdf_dir):
    """ Process regular data - this is more complex.. """
    pdf_page(session, url, base_url, 'tsuika', title, base_url, cache_dir, pdf_dir)


# There are three types of page, each with their own processor function
processors = {u'定期公表': teiki,
              u'解散分': kaisan,
              u'追加分': tsuika}


def check_dir(data_dir, create=False):
    if not os.path.isdir(data_dir):
        if create:
            logging.info("Creating new directory: %s" % data_dir)
            os.mkdir(data_dir)
        else:
            raise Exception("Data dir %s doesn't exist - use --mkdirs to create it." % data_dir)


def scrape_from(base_url, html_cache_dir, pdf_dir):
    logging.info("Starting at %s" % base_url)
    session = requests.Session()

    data = session.get(base_url).content
    # data = open('test.html').read()
    urls = get_urls(data)
    urls = filter(report_url_filter, urls)
    for href, text in urls:
        href = normalise(href, base_url)
        for k, p in processors.items():
            if k in text:
                p(session, href, text, base_url, html_cache_dir, pdf_dir)


def main():
    tooldir = os.path.dirname(os.path.abspath(__file__))

    CACHE_DIR = os.path.abspath(os.path.join(tooldir, '..', 'cache'))
    PDF_DIR = os.path.abspath(os.path.join(tooldir, '..', 'pdf'))

    SITE = 'http://www.soumu.go.jp'
    BASE_URL = SITE + '/senkyo/seiji_s/seijishikin/'

    from argparse import ArgumentParser

    p = ArgumentParser(description="Script to scrape contribution data from 総務省.")
    p.add_argument("--pdfdir", "-p", help="PDF file cache path", default=PDF_DIR)
    p.add_argument("--cachedir", "-c", help="html file cache path", default=CACHE_DIR)
    p.add_argument("--mkdirs", "-m", action="store_true", help="create cache and pdf dir if they don't exist")
    p.add_argument("--verbose", "-v", action="store_true", help="be more verbose")

    args = p.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    for data_dir in (args.cachedir, args.pdfdir):
        check_dir(data_dir, create=args.mkdirs)

    logging.debug("HTML cache is %s" % args.cachedir)
    logging.debug("PDF cache is %s" % args.pdfdir)

    scrape_from(BASE_URL, args.cachedir, args.pdfdir)

    logging.debug("Downloaded %d files." % _downloaded)


if __name__ == '__main__':
    main()
