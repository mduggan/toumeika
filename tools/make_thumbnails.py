#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
import logging
from argparse import ArgumentParser

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from shikin.pdf import pdfimages


def check_pdf(pdfdir, pdffile, pdf_root, thumbnail_root, force_regen, optimise):
    assert pdfdir.startswith(pdf_root)

    pdf_relative = pdfdir[len(pdf_root)+1:]
    thumbnailname = pdffile + '_thumb.png'
    thumbnaildir = os.path.join(thumbnail_root, pdf_relative)
    thumbnailpath = os.path.join(thumbnaildir, thumbnailname)

    if (not force_regen) and os.path.exists(thumbnailpath):
        return

    if not os.path.exists(thumbnaildir):
        logging.debug("Make dir %s" % thumbnaildir)
        os.makedirs(thumbnaildir)

    pdf_fullpath = os.path.join(pdfdir, pdffile)

    if 'main_content' in pdf_fullpath:
        # these have text content that needs rendering
        logging.debug("%s -> %s (render)" % (pdf_fullpath, thumbnailpath))
        pdfimages.render_page(pdf_fullpath, 1, thumbnailpath)
    else:
        # these are just images in a file
        for pngpath in pdfimages.extract_images(pdf_fullpath, firstpage=1, lastpage=1):
            logging.debug("%s -> %s" % (pngpath, thumbnailpath))
            os.rename(pngpath, thumbnailpath)


def main():
    pdf_root_default = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'pdf')
    thumbnail_root_default = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'static', 'thumbnails')

    p = ArgumentParser(description='Import scraped documents into the database')
    p.add_argument('--pdf-root',
                   help='Root directory of PDF files to make thumbnails for (default: ../pdf)',
                   default=pdf_root_default)
    p.add_argument('--thumbnail-root',
                   help='Root directory to put thumbnails in (default: ../static/thumbnails',
                   default=thumbnail_root_default)
    p.add_argument('--force-regen', '-f',
                   help='Regenerate all thumbnails, even those that already exist.',
                   action='store_true')
    p.add_argument('--no-optipng', '-n',
                   help='Do not use optipng on the output (much faster, larger pngs)',
                   action='store_true')
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
    if not os.path.isdir(args.thumbnail_root):
        p.error('thumbnail root is not a directory.')

    logging.info("Generating thumbnails for pdfs...")
    checked = 0

    pdf_root = os.path.abspath(args.pdf_root)
    thumbnail_root = os.path.abspath(args.thumbnail_root)

    for root, dirs, files in os.walk(pdf_root):
        pdf_files = filter(lambda x: x.endswith('.pdf'), files)
        if args.pattern:
            matches = set()
            for p in args.pattern:
                if p in root:
                    # directory match.. put them all in
                    matches = pdf_files
                    break
                matches.update(filter(lambda x: p in x, pdf_files))
            pdf_files = list(matches)
        if not pdf_files:
            continue
        for f in pdf_files:
            check_pdf(root, f, pdf_root, thumbnail_root, args.force_regen, not args.no_optipng)
            checked += 1
            if (checked % 1000) == 0:
                logging.info(".. %d pdfs checked." % checked)

    logging.info("FINISHED. %d pdfs checked." % checked)


if __name__ == '__main__':
    main()
