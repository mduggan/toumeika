Political contributions mini search engine
=======
A simple site to make political contribution data from the 総務省 more
searchable.

Requirements
------------
To run the site:
 * Flask
 * SQLAlchemy
 * Flask-Restless
 * Flask-SQLAlchemy
 * Flask-Babel

To do scraping:
 * requests
 * Poppler pdf utils
 * lxml

To make thumbnails:
 * optipng
 * ImageMagick

For running the OCR process:
 * Tesseract >=3.04 (+ eng and jpn lang packs)

Initialising
------------
This repo contains no data.  To fetch the data you need to:
 * Scrape PDFs from the 総務省 using `tools/scrape.py`
 * Initialise the DB with `./main.py initdb`
 * Generate thumbnails for the PDFs with `tools/make_thumbnails.py` - this can take a long time as it runs optipng on each doc - use `-n` to go faster and make slightly larger PNGs.
 * Import the documents into the database with `tools/importdocs.py` - ideally run this 3 times: 1. groups only (`-g`), 2. defer enabled (no options), 3. no-defer (`-n`).

Each tool has additional options that can be applied.  Run with `--help` to learn more.

License
-------
The code in this repository is made available under the BSD license.  See
LICENSE.
