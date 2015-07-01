#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import glob
import logging
import shlex
import re
import subprocess
from tmpdir import TemporaryDirectory

rot_re = re.compile("Page rot:       (\d+)")


def pdf_images(pdf_fullpath, optimise=True, autorotate=True, firstpage=0, lastpage=1):
    """
    Extract images from the given pdf using pdfimages.  Optionally
    automatically flip and rotate the images as they come out.  Yields a series
    of PNG paths.

    PNGs are created in a temporary directory, and can be moved or copied.  The
    directory and its contents will be deleted once the function completes.
    """
    if autorotate:
        # First decide if the pages are upside-down
        p = subprocess.Popen(['pdfinfo', pdf_fullpath], stdout=subprocess.PIPE)
        (stdoutdata, stderrdata) = p.communicate()

        rot = rot_re.search(stdoutdata)
        if not rot:
            logging.warn("Didn't get rot info for %s" % pdf_fullpath)
            rot = 0
        else:
            rot = int(rot.groups()[0])
    else:
        rot = 0

    with TemporaryDirectory() as tmpdirname:
        outfile_prefix = os.path.join(tmpdirname, 'thumb')
        lastpagestr = '-l %d' % lastpage if lastpage else ''
        command = 'pdfimages -p -f %d %s -png %s %s' % (firstpage, lastpagestr, pdf_fullpath, outfile_prefix)
        split = shlex.split(command)
        subprocess.call(split)
        outpattern = outfile_prefix + '-%03d-*.png'

        pageno = 1
        while glob.glob(outpattern % pageno):
            # there could be multiple images - find the big one.
            outfiles = glob.glob(outpattern % pageno)
            outfile = max(outfiles, key=lambda x: os.stat(x).st_size)
            logging.debug(" .. biggest is %s" % outfile)
            if rot:
                logging.debug("unflipping %s" % (outfile,))
                outfile_flip = outfile + '-flip.png'
                cmd = ['convert', outfile, '-rotate', str(rot), outfile_flip]
                subprocess.call(cmd)
                if not os.path.exists(outfile_flip):
                    logging.warn("%s didn't get made :(" % outfile_flip)
                else:
                    outfile = outfile_flip

            if optimise:
                logging.debug("Optimising %s" % (outfile,))
                subprocess.call(['optipng', '-q', outfile])

            yield outfile
            pageno += 1
