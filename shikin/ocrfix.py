import re

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
