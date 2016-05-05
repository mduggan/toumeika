#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Shikin, political donations database.
"""

from argparse import ArgumentParser

import shikin
import os
from shikin.model import GroupType, DocType, PubType, User, AppConfig


def initdb_command(args):
    """Creates the database tables."""
    db = shikin.app.dbobj
    db.create_all()
    print('Initialized the database.')

    # Seed some tables, if needed:
    groups = GroupType.query.count()
    if groups == 0:
        db.session.add(GroupType(u'議員別'))
        db.session.add(GroupType(u'政党本部'))
        db.session.add(GroupType(u'政党支部'))
        db.session.add(GroupType(u'政治資金団体'))
        db.session.add(GroupType(u'資金管理団体'))
        db.session.add(GroupType(u'その他の政治団体'))
        # An "unknown" type we can use when not sure
        db.session.add(GroupType(u'不明'))
    if groups < 8:
        db.session.add(GroupType(u'国会議員関係政治団体'))
        db.session.commit()

    doctypes = DocType.query.count()
    if doctypes == 0:
        db.session.add(DocType(u'政治資金収支報告書'))
        db.session.add(DocType(u'政党交付金使途等報告書'))
        db.session.add(DocType(u'政治資金収支報告書の要旨'))
        db.session.commit()

    pubtypes = PubType.query.count()
    if pubtypes == 0:
        db.session.add(PubType(u'定期公表'))
        db.session.add(PubType(u'解散分'))
        db.session.add(PubType(u'追加分'))
        db.session.add(PubType(u'解散支部分'))
        db.session.commit()

    users = User.query.count()
    if users == 0:
        db.session.add(User(name='admin', pw_hash='*', email='admin@toumeika.jp'))
        db.session.commit()

    configs = AppConfig.query.count()
    if configs == 0:
        db.session.add(AppConfig(key='secret_key', val=os.urandom(32)))
        db.session.commit()

    print('Seeded tables which need it.')


def dropdb_command(args):
    """Creates the database tables."""
    if not args.yes:
        print("Do you really want to drop the db? Add --yes if you're sure.")
        return
    shikin.app.dbobj.drop_all()
    print('dropped the database.')


def run_command(args):
    shikin.app.run(host=args.host, port=args.port, debug=not args.ndebug)


def startup(args):
    import logging
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    elif args.quiet:
        logging.basicConfig(level=logging.WARN)


def main():
    p = ArgumentParser(description="debug server for shikin")
    p.add_argument("--verbose", action="store_true", help="increase logging level")
    p.add_argument("--quiet", action="store_true", help="decrease logging level")
    sub = p.add_subparsers(dest='command', help='command help')

    init_sub = sub.add_parser("initdb", help="initialise the db")
    init_sub.set_defaults(func=initdb_command)

    drop_sub = sub.add_parser("dropdb", help="drop the db")
    drop_sub.add_argument("--yes", action="store_true", help="really drop the db")
    drop_sub.set_defaults(func=dropdb_command)

    run_sub = sub.add_parser("run", help="run the web app")
    run_sub.add_argument("--port", type=int, help="port to serve on", default=5000)
    run_sub.add_argument("--host", help="host to serve from (default=127.0.0.1)", default="127.0.0.1")
    run_sub.add_argument("--ndebug", help="disable debug mode", action="store_true")
    run_sub.set_defaults(func=run_command)

    args = p.parse_args()
    startup(args)
    args.func(args)


if __name__ == '__main__':
    main()
