#!/usr/bin/env python
"""
OCR Script which splits tables into cells and ocrs each one independantly.

Original table splitter from:
http://craiget.com/blog/extracting-table-data-from-pdfs-with-ocr/
"""

from PIL import Image
# from PIL import ImageOps
import subprocess
import sys
import os
import json
import logging
import requests
import shutil

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from shikin.pdf import pdfimages

API_BASE = 'http://localhost:5000/api/'
DOC_API = API_BASE + 'document/%d'
SEGMENT_API = API_BASE + 'raw/doc_segment'

DEBUG = True

# minimum run of adjacent pixels to call something a line
H_THRESH = 0.6
H_MIN_PX = 200
V_THRESH = 0.6
V_MIN_PX = 200
EDGE_ERODE = 4

MIN_COL_WIDTH = MIN_ROW_HEIGHT = 7

def get_vblocks(pix, w, h, thresh):
    """
    Get vertical blocks separated by large segments of white.
    """
    # allow a few black pixels per row..
    colthresh = 255 * 6
    colsums = [sum(255-pix[x, y] for y in range(h)) for x in range(w)]

    minx = 0
    maxx = w - 1
    while colsums[minx] < colthresh:
        minx += 1
    while colsums[maxx] < colthresh:
        maxx -= 1

    rowthresh = 255 * 6
    rowsums = [sum(255-pix[x, y] for x in range(minx, maxx)) for y in range(h)]

    whiteruns = []

    whitestart = 0
    y = 0
    while y < h:
        if rowsums[y] > rowthresh:
            # Black row
            if y - whitestart > 1:
                whiteruns.append((whitestart, y))
            whitestart = y
        y += 1
    if y - whitestart > 1:
        whiteruns.append((whitestart, y))

    y0 = 0
    if whiteruns[0][0] == 0:
        y0 = whiteruns[0][1]
        whiteruns.pop(0)

    for run in filter(lambda x: x[1] - x[0] >= thresh, whiteruns):
        yield (minx, y0, maxx, run[0])
        y0 = run[1]

    if h - y0 > thresh:
        yield (minx, y0, maxx, h)


def get_hlines(pix, w, h, thresh):
    """
    Get start/end pixels of lines containing horizontal runs of at least THRESH
    black pix
    """
    lines = []
    for y in range(h):
        x1, x2 = (None, None)
        best_x1, best_x2 = (None, None)
        black = 0
        run = 0
        for x in range(w):
            if pix[x, y] == 0:
                black += 1
                if x1 is None:
                    x1 = x
                x2 = x
            else:
                if black > run:
                    run = black
                    best_x1 = x1
                    best_x2 = x2
                    x1, x2 = (None, None)
                black = 0
        if black > run:
            run = black
            best_x1 = x1
            best_x2 = x2
        if run > thresh:
            lines.append((best_x1, y, best_x2, y))
    return lines


def get_vlines(pix, w, h, thresh, printlog=False):
    """
    Get start/end pixels of lines containing vertical runs of at least THRESH
    black pix
    """
    lines = []
    if printlog:
        print('get_vlines: %d, %d, %d' % (w, h, thresh))
    for x in range(w):
        y1, y2 = (None, None)
        best_y1, best_y2 = (None, None)
        black = 0
        run = 0
        for y in range(h):
            if pix[x, y] == 0:
                black += 1
                if y1 is None:
                    y1 = y
                y2 = y
            else:
                if black > run:
                    run = black
                    best_y1 = y1
                    best_y2 = y2
                    y1, y2 = (None, None)
                black = 0
        if black > run:
            run = black
            best_y1 = y1
            best_y2 = y2
        if run > thresh:
            lines.append((x, best_y1, x, best_y2))
        if printlog:
            print('%d (%s-%s): %d > %d?' % (x, best_y1, best_y2, run, thresh))
    return lines


def get_cols(vlines, w, h):
    """Get top-left and bottom-right coordinates for each column from a list of vertical lines"""
    if not len(vlines):
        return [(0, 0, w, h)]
    cols = []
    if vlines[0][0] > 1:
        # Area before the first line
        cols.append((0, 0, vlines[0][0], h))
    for i in range(1, len(vlines)):
        if vlines[i][0] - vlines[i-1][0] > 1:
            cols.append((vlines[i-1][0], vlines[i-1][1], vlines[i][2], vlines[i][3]))
    # TODO: add area after last col
    cols = filter(lambda x: x[2] - x[0] > MIN_COL_WIDTH, cols)
    return cols


def get_rows(hlines, w, h):
    """Get top-left and bottom-right coordinates for each row from a list of vertical lines"""
    if not len(hlines):
        return [(0, 0, w, h)]
    rows = []
    if hlines[0][0] > 1:
        # Area before the first line
        rows.append((0, 0, w, hlines[0][1]))
    for i in range(1, len(hlines)):
        if hlines[i][1] - hlines[i-1][3] > 1:
            rows.append((hlines[i-1][0], hlines[i-1][1], hlines[i][2], hlines[i][3]))
    # TODO: add area after last row
    rows = filter(lambda x: x[3] - x[1] > MIN_ROW_HEIGHT, rows)
    return rows


def get_cells(rows, cols):
    """Get top-left and bottom-right coordinates for each cell usings row and column coordinates"""
    cells = []
    for i, row in enumerate(rows):
        cells.append([None]*len(cols))
        for j, col in enumerate(cols):
            x1 = col[0]
            y1 = row[1]
            x2 = col[2]
            y2 = row[3]
            cells[i][j] = (x1, y1, x2, y2)
    return cells


def erode_edges(region, bgcol):
    pix = region.load()
    w, h = region.size

    for x in range(w):
        emax = min(x+1, EDGE_ERODE)
        emax = min(w-x, emax)
        if not emax:
            continue
        for y in range(0, emax):
            if pix[x, y] == bgcol:
                break
            pix[x, y] = bgcol
        for y in range(h-1, h-(emax+1), -1):
            if pix[x, y] == bgcol:
                break
            pix[x, y] = bgcol

    for y in range(h):
        emax = min(y+1, EDGE_ERODE)
        emax = min(h-y, emax)
        if not emax:
            continue
        for x in range(0, emax):
            if pix[x, y] == bgcol:
                break
            pix[x, y] = bgcol
        for x in range(w-1, w-(emax+1), -1):
            if pix[x, y] == bgcol:
                break
            pix[x, y] = bgcol


def ocr_cell(im, cells, x, y, tmpdir, pngfname):
    """Return OCRed text from this cell"""
    fbase = os.path.join("%s/%d-%d" % (tmpdir, x, y))
    ftif = "%s.tif" % fbase
    ftxt = "%s.txt" % fbase
    cmd = ["tesseract", "-l", "jpn+eng", ftif, fbase]
    # extract cell from whole image, grayscale (1-color channel), monochrome
    region = im.crop(cells[x][y])
    # region = ImageOps.grayscale(region)
    region = region.point(lambda p: p > 200 and 255)
    # determine background color (most used color)
    histo = region.histogram()
    black_ratio = float(histo[0])/histo[255]
    maybe_noisy = black_ratio > 0.33 and black_ratio < 3
    bgcolor = 0 if histo[0] > histo[255] else 255
    # trim remaining borders by finding top-left and bottom-right bg pixels

    # FIXME: this could go badly if there happens to be a lot of junk in TL or
    # BR.
    if DEBUG:
        region.save(pngfname + '-preerode-' + os.path.split(ftif)[1], "TIFF")

    erode_edges(region, bgcolor)

    # save as TIFF and extract text with Tesseract OCR
    logging.debug("ocr cell %d %d (bg %d) %dx%d" % (x, y, bgcolor, region.size[0], region.size[1]))
    region.save(ftif, "TIFF")
    if DEBUG:
        region.save(pngfname + '-' + os.path.split(ftif)[1], "TIFF")

    subprocess.call(cmd, stderr=subprocess.PIPE)
    lines = filter(lambda x: x, [l.strip() for l in open(ftxt).readlines()])

    if DEBUG:
        shutil.copyfile(ftxt, pngfname + '-' + os.path.split(ftxt)[1])

    # TODO: Maybe deskew here.  convert $in -deskew 10 $out

    if maybe_noisy and not lines:
        logging.debug("Got nothing on noisy img: filter and run again")
        filtertif = ftif+'-filtered.tif'
        cmd2 = ["convert", ftif, "-morphology", "close", "square:1", filtertif]
        subprocess.call(cmd2, stderr=subprocess.PIPE)
        if DEBUG:
            shutil.copyfile(filtertif, pngfname + '-' + os.path.split(filtertif)[1])
        cmd3 = ["tesseract", "-l", "jpn+eng", filtertif, fbase]
        subprocess.call(cmd3, stderr=subprocess.PIPE)
        lines = filter(lambda x: x, [l.strip() for l in open(ftxt).readlines()])
        if DEBUG:
            shutil.copyfile(ftxt, pngfname + '-' + os.path.split(ftxt)[1] + '-filtered.txt')

    return '\n'.join(lines)


def get_image_data(filename):
    """Extract textual data[rows][cols] from spreadsheet-like image file"""
    tmpdir, pngfname = os.path.split(filename)
    logging.debug("processing %s" % pngfname)
    im = Image.open(filename)
    allpix = im.load()
    assert im.mode == '1'
    totwidth, totheight = im.size
    blockno = 0
    for (x1, y1, x2, y2) in get_vblocks(allpix, totwidth, totheight, 20):
        crop = im.crop((x1, y1, x2, y2))
        if DEBUG:
            crop.save('%s-%d-%d-%d-%d-%d.png' % (pngfname, blockno, x1, y1, x2, y2))
        pix = crop.load()

        (cropw, croph) = crop.size
        logging.info("%s:%d: (%d,%d)-(%d-%d)" % (pngfname, blockno, x1, y1, x2, y2))
        hthresh = max(H_MIN_PX, int((cropw) * H_THRESH))
        hlines = get_hlines(pix, cropw, croph, hthresh)
        vthresh = max(V_MIN_PX, int((croph) * V_THRESH))
        vlines = get_vlines(pix, cropw, croph, vthresh)
        logging.debug("%s block %d: hlines: %d  vlines: %d" % (pngfname, blockno, len(hlines), len(vlines)))

        # TODO: fill white on the lines before cropping out cells.  That should
        # solve the "I" problem and improve overall quality.

        rows = get_rows(hlines, cropw, croph)
        cols = get_cols(vlines, cropw, croph)
        logging.debug("%s block %d: rows: %d, cols: %d" % (pngfname, blockno, len(rows), len(cols)))
        cells = get_cells(rows, cols)

        for row in range(len(rows)):
            for col in range(len(cols)):
                text = ocr_cell(crop, cells, row, col, tmpdir, '%s-%d' % (pngfname, blockno))
                if text:
                    c = cells[row][col]
                    cx1 = x1 + c[0]
                    cy1 = y1 + c[1]
                    cx2 = x1 + c[2]
                    cy2 = y1 + c[3]
                    yield (blockno, row, col, (cx1, cy1, cx2, cy2), text)
        blockno += 1


def extract_pdf(filename):
    """Extract table data from pdf"""
    # extract table data from each page
    logging.debug("extracting images from %s" % filename)
    fileno = 0
    for pngfile in pdfimages.pdf_images(filename, optimise=False, firstpage=1, lastpage=200):
        # TODO: Maybe run unpaper on the PNG file to remove skew, rotation, and
        # noise.
        for (blockno, row, col, location, text) in get_image_data(pngfile):
            yield (fileno, blockno, row, col, location, text)
        fileno += 1


def main():
    from argparse import ArgumentParser

    p = ArgumentParser(description="Script to OCR documents with tables inside.")
    p.add_argument("--verbose", "-v", action="store_true", help="be more verbose")
    p.add_argument("--debug", "-d", action="store_true", help="dump debug images and ocr output")
    p.add_argument('pdf', nargs='+', help='pdf filename or database doc id')

    args = p.parse_args()

    global DEBUG
    DEBUG = args.debug

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    for filename in args.pdf:
        # split target pdf into pages
        docid = None
        s = requests.session()
        s.headers['Content-Type'] = 'application/json'
        filename = sys.argv[1]
        if filename.isdigit():
            docdata = s.get(DOC_API % int(filename)).json()
            if len(docdata['segments']):
                logging.error("Doc already has segments in DB.  Use --force to clear them.")
                continue
            path = docdata['docset']['path']
            docid = docdata['id']
            if path[0] == '/':
                path = path[1:]
            fname = docdata['filename']
            filename = os.path.join('..', 'pdf', path, fname)
        if not os.path.exists(filename):
            logging.error("File %s doesn't exist." % filename)
            continue

        # print('pageno\tblockno\trow\tcol\ttext')
        for (pageno, blockno, row, col, location, text) in extract_pdf(filename):
            print("%d\t%d\t%d\t%d\t%s\t%s" % (pageno, blockno, row, col, location, 'text'))
            if docid:
                obj = {'doc_id': docid, 'page': pageno, 'row': row, 'col': col,
                       'x1': location[0], 'y1': location[1], 'x2': location[2],
                       'y2': location[3], 'ocrtext': text}
                result = s.post(SEGMENT_API, data=json.dumps(obj))
                try:
                    j = result.json()
                except ValueError:
                    import pdb; pdb.set_trace()
                    pass


if __name__ == '__main__':
    main()
