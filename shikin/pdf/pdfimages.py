#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import glob
import logging
import shlex
import subprocess
from tmpdir import TemporaryDirectory
from .util import get_rot, optimise_png, rotate_png


def extract_images(pdf_fullpath, optimise=True, autorotate=True, firstpage=1, lastpage=1):
    """
    Extract images from the given pdf using pdfimages.  Optionally
    automatically flip and rotate the images as they come out.  Yields a series
    of PNG paths.  Pages are 1-indexed!

    PNGs are created in a temporary directory, and can be moved or copied.  The
    directory and its contents will be deleted once the function completes.
    """
    if autorotate:
        rot = get_rot(pdf_fullpath)
    else:
        rot = 0

    with TemporaryDirectory() as tmpdirname:
        outfile_prefix = os.path.join(tmpdirname, 'thumb')
        lastpagestr = '-l %d' % lastpage if lastpage else ''
        command = 'pdfimages -p -f %d %s -png "%s" "%s"' % (firstpage, lastpagestr, pdf_fullpath, outfile_prefix)
        split = shlex.split(command)
        subprocess.call(split)
        outpattern = outfile_prefix + '-%03d-*.png'

        pageno = firstpage
        while glob.glob(outpattern % pageno):
            # there could be multiple images - find the big one.
            outfiles = glob.glob(outpattern % pageno)
            outfile = max(outfiles, key=lambda x: os.stat(x).st_size)
            logging.debug(" .. biggest is %s" % outfile)
            outfile = rotate_png(outfile, rot)

            if optimise:
                outfile = optimise_png(outfile)

            yield outfile
            pageno += 1


def render_page(pdf_fullpath, pageno, dest, autorotate=True):
    # TODO: autorotate?
    try:
        command = 'convert -density 200 "%s"[%d] "%s"' % (pdf_fullpath, pageno - 1, dest)
        split = shlex.split(command)
        subprocess.call(split)
    except Exception, e:
        logging.error('Conversion error: %s' % str(e))
        try:
            # Remove the output on any error
            os.unlink(dest)
        except:
            pass
