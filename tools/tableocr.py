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
MAX_LINE_DRIFT = 10
MIN_COL_WIDTH = MIN_ROW_HEIGHT = 20
NOSIE_RATIO = 5.0
MIN_FILLED_PX = 20


class Box():
    def __init__(self, x1, y1, x2, y2):
        self.x1 = min(x1, x2)
        self.x2 = max(x1, x2)
        self.y1 = min(y1, y2)
        self.y2 = max(y1, y2)

    @property
    def width(self):
        return self.x2 - self.x1

    @property
    def height(self):
        return self.y2 - self.y1

    @property
    def midx(self):
        return self.x1 + (self.x2 - self.x1)/2

    @property
    def midy(self):
        return self.y1 + (self.y2 - self.y1)/2

    @property
    def tup(self):
        return (self.x1, self.y1, self.x2, self.y2)

    @property
    def tostr(self):
        return '%d-%d-%d-%d' % (self.x1, self.y1, self.x2, self.y2)

    @property
    def pxcount(self):
        return (self.x2-self.x1)*(self.y2-self.y1)

    def offset(self, x, y):
        return Box(self.x1+x, self.y1+y, self.x2+x, self.y2+y)

    def __repr__(self):
        return '(%d,%d)-(%d,%d)' % (self.x1, self.y1, self.x2, self.y2)


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
        yield Box(minx, y0, maxx, run[0])
        y0 = run[1]

    if h - y0 > thresh:
        yield Box(minx, y0, maxx, h)


def get_hlines(pix, w, h, thresh):
    """
    Get start/end pixels of lines containing horizontal runs of at least THRESH
    black pix
    """
    lines = []
    for y in range(h):
        thisy = y
        x1, x2 = (None, None)
        best_x1, best_x2 = (None, None)
        black = 0
        run = 0
        for x in range(w):
            if black > 20 and pix[x, thisy] != 0 and abs(y - thisy) < MAX_LINE_DRIFT:
                # ran off a good line - tweak y to see if it is sloped
                if thisy > 0 and pix[x, thisy-1] == 0:
                    thisy -= 1
                elif thisy < h-1 and pix[x, thisy+1] == 0:
                    thisy += 1

            if pix[x, thisy] == 0:
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
            lines.append(Box(best_x1, min(y, thisy), best_x2, max(y, thisy)))
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
        thisx = x
        y1, y2 = (None, None)
        best_y1, best_y2 = (None, None)
        black = 0
        run = 0
        for y in range(h):
            if black > 20 and pix[thisx, y] != 0 and abs(x - thisx) < MAX_LINE_DRIFT:
                # ran off a good line - tweak x to see if it is sloped
                if thisx > 0 and pix[thisx-1, y] == 0:
                    thisx -= 1
                elif thisx < w-1 and pix[thisx+1, y] == 0:
                    thisx += 1

            if pix[thisx, y] == 0:
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
            lines.append(Box(min(x, thisx), best_y1, max(x, thisx), best_y2))
        if printlog:
            print('(%d,%s)-(%d,%s): %d > %d?' % (x, best_y1, thisx, best_y2, run, thresh))
    return lines


def get_cols(vlines, w, h):
    """Get top-left and bottom-right coordinates for each column from a list of vertical lines"""
    if not len(vlines):
        return [Box(0, 0, w, h)]
    cols = []

    # Area before the first vline
    if vlines[0].y1 > 1:
        cols.append(Box(0, 0, vlines[0].midx, h))

    for i in range(1, len(vlines)):
        cols.append(Box(vlines[i-1].midx, vlines[i-1].midy, vlines[i].midx, vlines[i].midy))

    # Area after last vline
    if w - vlines[-1].midx > 1:
        cols.append(Box(vlines[-1].midx, 0, w, h))
    cols = filter(lambda x: x.width > MIN_COL_WIDTH, cols)
    return cols


def get_rows(hlines, w, h):
    """Get top-left and bottom-right coordinates for each row from a list of vertical lines"""
    if not len(hlines):
        return [Box(0, 0, w, h)]
    rows = []

    # Area before the first hline
    if hlines[0].x1 > 1:
        rows.append(Box(0, 0, w, hlines[0].midy))

    for i in range(1, len(hlines)):
        rows.append(Box(hlines[i-1].midx, hlines[i-1].midy, hlines[i].midx, hlines[i].midy))

    # Area after last hline
    if h - hlines[-1].y2 > 1:
        rows.append(Box(0, hlines[-1].midy, w, h))

    rows = filter(lambda x: x.height > MIN_ROW_HEIGHT, rows)
    return rows


def get_cells(rows, cols, w, h):
    """Get top-left and bottom-right coordinates for each cell usings row and column coordinates"""
    cells = []
    for i, row in enumerate(rows):
        cells.append([None]*len(cols))
        for j, col in enumerate(cols):
            cells[i][j] = Box(col.x1, row.y1, col.x2, row.y2)
    return cells


def erode_edges(region, bgcol):
    """
    Move in from the edge and clear the image until we find a bgcol pixel.

    Erodes a maximum of EDGE_ERODE pixels in from each side of the image.
    """
    pix = region.load()
    w, h = region.size
    erode_x = min(h, EDGE_ERODE)
    erode_y = min(w, EDGE_ERODE)

    # top and bottom
    for x in range(w):
        emax = min(x+1, erode_x)
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

    # left and right
    for y in range(h):
        emax = min(y+1, erode_y)
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
    region = im.crop(cells[x][y].tup)
    # region = ImageOps.grayscale(region)
    region = region.point(lambda p: p > 200 and 255)
    # determine background color (most used color)
    histo = region.histogram()
    black_ratio = float(histo[0])/(histo[255]+0.01)
    maybe_noisy = black_ratio > 1/NOSIE_RATIO and black_ratio < NOSIE_RATIO
    bgcolor = 0 if histo[0] > histo[255] else 255

    if DEBUG:
        region.save(pngfname + '-preerode-' + os.path.split(ftif)[1], "TIFF")

    # trim remaining borders by finding first white pixel going in from edge
    erode_edges(region, bgcolor)
    histo = region.histogram()

    if histo[bgcolor]+MIN_FILLED_PX > cells[x][y].pxcount:
        logging.debug("ocr cell %d %d seems empty." % (x, y))
        return None

    # save as TIFF and extract text with Tesseract OCR
    logging.debug("ocr cell %d %d (bg %d) %dx%d" % (x, y, bgcolor, region.size[0], region.size[1]))
    region.save(ftif, "TIFF")
    if DEBUG:
        region.save(pngfname + '-' + os.path.split(ftif)[1], "TIFF")

    subprocess.call(cmd, stderr=subprocess.PIPE)
    lines = filter(lambda x: x, [l.strip() for l in open(ftxt).readlines()])

    if DEBUG:
        shutil.copyfile(ftxt, pngfname + '-' + os.path.split(ftxt)[1])

    if maybe_noisy and not lines:
        logging.debug("Got nothing on noisy img: filter and run again")
        filtertif = ftif+'-filtered.tif'
        cmd2 = ["convert", ftif, "-morphology", "close", "square:1", filtertif]
        subprocess.call(cmd2, stderr=subprocess.PIPE)
        ftif = filtertif
        cmd = ["tesseract", "-l", "jpn+eng", ftif, fbase]
        if DEBUG:
            shutil.copyfile(ftif, pngfname + '-' + os.path.split(ftif)[1])
        subprocess.call(cmd, stderr=subprocess.PIPE)
        lines = filter(lambda x: x, [l.strip() for l in open(ftxt).readlines()])
        if DEBUG:
            shutil.copyfile(ftxt, pngfname + '-' + os.path.split(ftxt)[1] + '-filtered.txt')

    if not lines:
        logging.debug("Retrying with PSM 8")
        cmd4 = ["tesseract", "-l", "jpn+eng", "-psm", "8", ftif, fbase]
        subprocess.call(cmd4, stderr=subprocess.PIPE)
        if DEBUG:
            shutil.copyfile(ftxt, pngfname + '-' + os.path.split(ftxt)[1] + '-psm8.txt')

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
    for box in get_vblocks(allpix, totwidth, totheight, 20):
        crop = im.crop(box.tup)
        if DEBUG:
            crop.save('%s-%d-%s.png' % (pngfname, blockno, box.tostr))
        pix = crop.load()

        (cropw, croph) = crop.size
        logging.info("%s:%d: %s" % (pngfname, blockno, box))
        hthresh = max(H_MIN_PX, int((cropw) * H_THRESH))
        hlines = get_hlines(pix, cropw, croph, hthresh)
        vthresh = max(V_MIN_PX, int((croph) * V_THRESH))
        vlines = get_vlines(pix, cropw, croph, vthresh)
        logging.debug("%s block %d: hlines: %d  vlines: %d" % (pngfname, blockno, len(hlines), len(vlines)))

        rows = get_rows(hlines, cropw, croph)
        cols = get_cols(vlines, cropw, croph)
        logging.debug("%s block %d: rows: %d, cols: %d" % (pngfname, blockno, len(rows), len(cols)))
        cells = get_cells(rows, cols, cropw, croph)

        for row in range(len(rows)):
            for col in range(len(cols)):
                text = ocr_cell(crop, cells, row, col, tmpdir, '%s-%d' % (pngfname, blockno))
                if text is not None:
                    c = cells[row][col]
                    yield (blockno, row, col, c.offset(box.x1, box.y1), text)
        blockno += 1


def extract_pdf(filename, pageno):
    """Extract table data from pdf"""
    # extract table data from each page
    logging.debug("extracting images from %s" % filename)
    fileno = 0

    firstpage = pageno or 1
    lastpage = pageno

    for pngfile in pdfimages.pdf_images(filename, optimise=False, firstpage=firstpage, lastpage=lastpage):
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
    p.add_argument("--page", "-p", type=int, help="single page number to run")
    p.add_argument("--force", "-f", action="store_true", help="continue even if segments already in db (identical ones will be ignored)")

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
        existing_segments = {}
        s = requests.session()
        s.headers['Content-Type'] = 'application/json'
        filename = sys.argv[1]
        if filename.isdigit():
            docdata = s.get(DOC_API % int(filename)).json()
            if len(docdata['segments']):
                if not args.force:
                    logging.error("Doc already has segments in DB.  Use --force to continue.")
                    continue
                segments = docdata['segments']
                for seg in segments:
                    existing_segments[(seg['page'], seg['x1'], seg['y1'], seg['x2'], seg['y2'])] = seg
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
        for (pageno, blockno, row, col, loc, text) in extract_pdf(filename, args.page):
            print("%d\t%d\t%d\t%d\t%s\t%s" % (pageno, blockno, row, col, loc, 'text'))
            if docid:
                if (pageno, loc.x1, loc.y1, loc.x2, loc.y2) in existing_segments:
                    logging.info("Already in DB, skipping")
                    continue
                obj = {'doc_id': docid, 'page': pageno, 'row': row, 'col': col,
                       'x1': loc.x1, 'y1': loc.y1, 'x2': loc.x2,
                       'y2': loc.y2, 'ocrtext': text}
                result = s.post(SEGMENT_API, data=json.dumps(obj))
                try:
                    j = result.json()
                except ValueError:
                    import pdb; pdb.set_trace()
                    pass


if __name__ == '__main__':
    main()
