#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import logging
import shlex
import re
import subprocess
from tmpdir import TemporaryDirectory
from argparse import ArgumentParser

rot_re = re.compile("Page rot:       (\d+)")

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

    # First decide if the pages are upside-down
    p = subprocess.Popen(['pdfinfo', pdf_fullpath], stdout=subprocess.PIPE)
    (stdoutdata, stderrdata) = p.communicate()

    rot = rot_re.search(stdoutdata)
    if not rot:
        logging.warn("Didn't get rot info for %s" % pdffile)
        rot = 0
    else:
        rot = int(rot.groups()[0])

    with TemporaryDirectory() as tmpdirname:
        outfile_prefix = os.path.join(tmpdirname, 'thumb')
        command = 'pdfimages -f 0 -l 1 -png %s %s' % (pdf_fullpath, outfile_prefix)
        split = shlex.split(command)
        subprocess.call(split)
        outfile = outfile_prefix + '-000.png'
        if not os.path.exists(outfile):
            logging.warn("%s didn't get made :(" % outfile)
            return
        else:
            if rot:
                logging.debug("unflipping %s" % (outfile,))
                outfile_flip = outfile + '-flip.png'
                cmd = ['convert', outfile, '-rotate', str(rot), outfile_flip]
                subprocess.call(cmd)
                if not os.path.exists(outfile_flip):
                    logging.warn("%s didn't get made :(" % outfile_flip)
                else:
                    outfile = outfile_flip

            logging.debug("Optimising %s" % (outfile,))
            if optimise:
                subprocess.call(['optipng', '-q', outfile])

            logging.debug("%s -> %s" % (outfile, thumbnailpath))
            os.rename(outfile, thumbnailpath)


def main():
    pdf_root_default = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'pdf')
    thumbnail_root_default = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'static', 'thumbnails')

    p = ArgumentParser(description='Import scraped documents into the database')
    p.add_argument('--pdf-root',
                   help='Root directory of PDF files to import (default: ../pdf)',
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
