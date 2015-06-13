def size_str(size):
    sizes = ['b', 'kb', 'Mb', 'Gb', 'Tb']
    for s in sizes:
        if size < 1024:
            return '%.01f%s' % (size, s)
        size /= 1024.0
    return 'really big.'
