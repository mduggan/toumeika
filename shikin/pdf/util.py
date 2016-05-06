#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import re
import subprocess
import os

_rot_re = re.compile("Page rot:       (\d+)")


def get_rot(pdf_fullpath):
    # First decide if the pages are upside-down
    p = subprocess.Popen(['pdfinfo', pdf_fullpath], stdout=subprocess.PIPE)
    (stdoutdata, stderrdata) = p.communicate()

    rot = _rot_re.search(stdoutdata)
    if not rot:
        logging.warn("Didn't get rot info for %s" % pdf_fullpath)
        rot = 0
    else:
        rot = int(rot.groups()[0])
    return rot


def optimise_png(path):
    logging.debug("Optimising %s" % (path,))
    subprocess.call(['optipng', '-q', path])
    return path


def rotate_png(path, rot):
    if not rot:
        return path
    logging.debug("unflipping %s" % (path,))
    path_flip = path + '-flip.png'
    cmd = ['convert', path, '-rotate', str(rot), path_flip]
    subprocess.call(cmd)
    if not os.path.exists(path_flip):
        logging.warn("%s didn't get made :(" % path_flip)
    else:
        path = path_flip
    return path
