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
import logging

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from shikin.pdf import pdfimages

DEBUG = True

# minimum run of adjacent pixels to call something a line
H_THRESH = 0.6
H_MIN_PX = 200
V_THRESH = 0.6
V_MIN_PX = 200


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
        black = 0
        run = 0
        for x in range(w):
            if pix[x, y] == 0:
                black += 1
                if not x1:
                    x1 = x
                x2 = x
            else:
                if black > run:
                    run = black
                black = 0
        if run > thresh:
            lines.append((x1, y, x2, y))
    return lines


def get_vlines(pix, w, h, thresh):
    """
    Get start/end pixels of lines containing vertical runs of at least THRESH
    black pix
    """
    lines = []
    for x in range(w):
        y1, y2 = (None, None)
        black = 0
        run = 0
        for y in range(h):
            if pix[x, y] == 0:
                black += 1
                if not y1:
                    y1 = y
                y2 = y
            else:
                if black > run:
                    run = black
                black = 0
        if run > thresh:
            lines.append((x, y1, x, y2))
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


def ocr_cell(im, cells, x, y, tmpdir):
    """Return OCRed text from this cell"""
    fbase = os.path.join("%s/%d-%d" % (tmpdir, x, y))
    ftif = "%s.tif" % fbase
    ftxt = "%s.txt" % fbase
    cmd = ["tesseract", "-l", "jpn+eng", ftif, fbase]
    # extract cell from whole image, grayscale (1-color channel), monochrome
    region = im.crop(cells[x][y])
    #region = ImageOps.grayscale(region)
    region = region.point(lambda p: p > 200 and 255)
    # determine background color (most used color)
    histo = region.histogram()
    bgcolor = 0 if histo[0] > histo[255] else 255
    # trim remaining borders by finding top-left and bottom-right bg pixels
    pix = region.load()
    x1, y1 = 0, 0
    x2, y2 = region.size
    x2, y2 = x2-1, y2-1
    while pix[x1, y1] != bgcolor and x1 < x2 and y1 < y2:
        x1 += 1
        y1 += 1
    while pix[x2, y2] != bgcolor and x2 > 0 and y2 > 0:
        x2 -= 1
        y2 -= 1
    # save as TIFF and extract text with Tesseract OCR
    trimmed = region.crop((x1, y1, x2, y2))
    logging.debug("region trim (%d,%d,%d,%d)" % (x1, y1, x2, y2))
    if x1 >= x2 or y1 >= y2:
        logging.debug("nothing left.")
        return ''
    trimmed.save(ftif, "TIFF")
    subprocess.call(cmd, stderr=subprocess.PIPE)
    lines = filter(lambda x: x, [l.strip() for l in open(ftxt).readlines()])
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
            crop.save(os.path.join(tmpdir, '%s-%d-%d-%d-%d.png' % (pngfname, x1, y1, x2, y2)))
        pix = crop.load()

        cropw = x2 - x1
        croph = y2 - y1
        logging.info("%s: (%d,%d)-(%d-%d)" % (pngfname, x1, y1, y1, y2))
        hthresh = max(H_MIN_PX, int((cropw) * H_THRESH))
        hlines = get_hlines(pix, cropw, croph, hthresh)
        logging.info("%s: hlines: %d" % (pngfname, len(hlines)))
        vthresh = max(V_MIN_PX, int((croph) * V_THRESH))
        vlines = get_vlines(pix, cropw, croph, vthresh)
        logging.info("%s: vlines: %d" % (pngfname, len(vlines)))

        # TODO: fill white on the lines before cropping out cells.  That should
        # solve the "I" problem and improve overall quality.

        rows = get_rows(hlines, cropw, croph)
        logging.info("%s: rows: %d" % (pngfname, len(rows)))
        cols = get_cols(vlines, cropw, croph)
        logging.info("%s: cols: %d" % (pngfname, len(cols)))
        cells = get_cells(rows, cols)

        for row in range(len(rows)):
            for col in range(len(cols)):
                text = ocr_cell(crop, cells, row, col, tmpdir)
                if text:
                    yield (blockno, row, col, text)
        blockno += 1


def extract_pdf(filename):
    """Extract table data from pdf"""
    # extract table data from each page
    logging.debug("extracting images from %s" % filename)
    fileno = 0
    for pngfile in pdfimages.pdf_images(filename, optimise=False, firstpage=0, lastpage=4):

        # TODO: Run unpaper on the PNG file to remove skew, rotation, and
        # noise.

        for (blockno, row, col, text) in get_image_data(pngfile):
            yield (fileno, blockno, row, col, text)
        fileno += 1
        import pdb; pdb.set_trace()


if __name__ == '__main__':
    if DEBUG:
        logging.basicConfig(level=logging.DEBUG)
    if len(sys.argv) != 2:
        print("Usage: %s FILENAME" % sys.argv[0])
    else:
        # split target pdf into pages
        filename = sys.argv[1]
        print('pageno\tblockno\trow\tcol\ttext')
        for (pageno, blockno, row, col, text) in extract_pdf(filename):
            print("%d\t%d\t%d\t%d\t%s" % (pageno, blockno, row, col, text))
