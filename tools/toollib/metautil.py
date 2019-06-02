# -*- coding: utf-8 -*-

import os

"""
Functions for working with metadata files which we keep with the pdf files.

These are used to record information that was downloaded with the pdf files and
are just an intermediate step before going into the database.
"""


def is_meta_path(path):
    return path.endswith('_meta.txt')


def meta_path(pdf_path):
    return pdf_path + '_meta.txt'


def get_meta(pdf_path):
    """
    Return the dictionary of metadata for the given pdf
    """
    meta_file = meta_path(pdf_path)

    if not os.path.isfile(meta_file):
        return None

    meta = open(meta_file).readlines()
    try:
        meta = dict(x.strip().decode('utf-8').split(',') for x in meta)
    except ValueError:
        print("ERROR reading meta for %s!" % pdf_path)
        raise

    return meta


def dump_meta(meta):
    for k, v in meta.items():
        print("%s\t%s" % (k, v))
