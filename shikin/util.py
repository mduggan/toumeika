from flask import request, session
from werkzeug import check_password_hash, generate_password_hash


def size_str(size):
    sizes = ['b', 'kb', 'Mb', 'Gb', 'Tb']
    for s in sizes:
        if size < 1024:
            return '%.01f%s' % (size, s)
        size /= 1024.0
    return 'really big.'


def dologin():
    from .model import User
    """
    Check a login posted in the current request.  Return (user, error), one of
    which will be null.
    """
    error = None
    user = User.query.filter(User.name == request.form['username']).first()
    if user is None:
        error = 'Invalid username'
    elif not check_password_hash(user.pw_hash,
                                 request.form['password']):
        error = 'Invalid password'
        user = None
    else:
        session['username'] = user.name
    return user, error
