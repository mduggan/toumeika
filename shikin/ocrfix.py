import re
from collections import Counter
import editdistance

from .model import DocSegmentReview, DocSegment

number_re = re.compile('(\d{1,3})(([., ]{1,2}\d\d\d)+)')


def guess_line_fix(s):
    nm = number_re.match(s)
    if nm:
        data = nm.groups()
        num = data[0] + data[1].replace(' ', '').replace('.', '').replace(',', '')
        return "{:,}".format(int(num))

    s = s.replace(' ', '')
    return s


def guess_fix(s):
    return '\n'.join([guess_line_fix(l) for l in s.splitlines()])


def suggestions(seg, n=5):
    """
    Collect up to n OCR corrections which are for similar segments to the
    given one.  Similar in this context means appearing in the same column.
    """
    q = DocSegmentReview.query.join(DocSegment)\
                        .filter(DocSegmentReview.text != seg.ocrtext)\
                        .filter(DocSegment.x1 >= seg.x1-50)\
                        .filter(DocSegment.x2 <= seg.x2+50)\
                        .order_by(DocSegmentReview.rev.desc())

    currenttxt = seg.besttext
    similar = q.all()
    texts = []
    seen = set()
    for s in similar:
        if s.segment_id in seen:
            continue
        texts.append(s.text)
        seen.add(s.segment_id)

    c = Counter(texts)



    return [x[0] for x in c.most_common(n)]
