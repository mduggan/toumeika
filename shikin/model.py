# -*- coding: utf-8 -*-
"""Database model for political contributions documents"""

import os
from sqlalchemy import Column, ForeignKey, Integer, Text, Date, DateTime, BLOB, UniqueConstraint, func
from sqlalchemy.orm import relationship, backref

from . import util
from . import app

Model = app.dbobj.Model


class AppConfig(Model):
    id = Column('id', Integer(), primary_key=True)
    key = Column('key', Text(), nullable=False, index=True, unique=True)
    val = Column('val', BLOB(), nullable=False, unique=True)


class GroupType(Model):
    """The type of group (eg, 政党の支部)"""
    id = Column('id', Integer(), primary_key=True)
    name = Column('name', Text(), nullable=False, index=True, unique=True)

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return 'GroupType<%d:%s>' % (self.id, self.name)


class Group(Model):
    """A political group to which a particular document can relate"""
    id = Column('id', Integer(), primary_key=True)
    name = Column('name', Text(), nullable=False, index=True, unique=True)
    type_id = Column('type_id', Text(), ForeignKey(GroupType.id), nullable=False, index=True)
    parent_id = Column('parent_id', Integer(), ForeignKey(id), nullable=True, index=True)

    children = relationship('Group', backref=backref('parent', remote_side=[id]))
    type = relationship(GroupType, uselist=False)
    docs = relationship('Document', uselist=True)

    @property
    def doccount(self):
        return len(self.docs)

    @property
    def minyear(self):
        q = app.dbobj.session.query(func.min(Document.year)).filter(Document.group_id == self.id)
        y = q.first()
        return y[0] if y else None

    @property
    def maxyear(self):
        q = app.dbobj.session.query(func.max(Document.year)).filter(Document.group_id == self.id)
        y = q.first()
        return y[0] if y else None

    def __repr__(self):
        return 'Group<%d:%s>' % (self.id, self.name)


class DocType(Model):
    """A document type, (eg, 政治資金収支報告書)"""
    id = Column('id', Integer(), primary_key=True)
    name = Column('name', Text(), nullable=False, index=True, unique=True)

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return 'DocType<%d:%s>' % (self.id, self.name)


class PubType(Model):
    """Publication type (eg, 解散分 or 追加分)"""
    id = Column('id', Integer(), primary_key=True)
    name = Column('name', Text(), nullable=False, index=True, unique=True)

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return 'PubType<%d:%s>' % (self.id, self.name)


class DocSet(Model):
    """A set of documents published together."""
    id = Column('id', Integer(), primary_key=True)
    published = Column('published', Date(), nullable=False, index=True)
    pubtype_id = Column('pubtype_id', Integer(), ForeignKey(PubType.id), nullable=False, index=True)
    doctype_id = Column('doctype_id', Integer(), ForeignKey(DocType.id), nullable=False, index=True)
    path = Column('path', Text(), nullable=False, index=True)

    unique_docset = UniqueConstraint('published', 'pubtype_id', 'doctype_id')

    doctype = relationship(DocType, uselist=False)
    pubtype = relationship(PubType, uselist=False)

    def __repr__(self):
        return 'DocSet<%d:%s>' % (self.id, self.path)


class Document(Model):
    """A single document (pdf file)"""
    id = Column('id', Integer(), primary_key=True)
    docset_id = Column('docset_id', Integer(), ForeignKey(DocSet.id), nullable=False, index=True)
    # Note: document years use western calendar.
    # This is the year to which the document relates, not the year of publication.
    # date of publication will be in the docset.
    year = Column('year', Integer())
    group_id = Column('group_id', Integer(), ForeignKey(Group.id), index=True)
    note = Column('note', Text(), nullable=True, index=True)
    filename = Column('path', Text(), nullable=False, index=True)
    pages = Column('pages', Integer(), nullable=False)
    # file size in bytes..
    size = Column('size', Integer(), nullable=False, index=True)

    # URL the pdf was downloaded from
    url = Column('url', Text(), nullable=False, unique=True, index=True)
    # URL of the page that pointed to this pdf
    srcurl = Column('srcurl', Text(), nullable=False)

    group = relationship(Group, uselist=False)
    docset = relationship(DocSet, uselist=False)

    @property
    def size_str(self):
        return util.size_str(self.size)

    @property
    def path(self):
        return os.path.join(self.docset.path, self.filename)

    def __repr__(self):
        return 'Document<%d:%s>' % (self.id, self.filename)


class Tag(Model):
    """A tag which can be placed on a document"""
    id = Column('id', Integer(), primary_key=True)
    name = Column('name', Text(), nullable=False, index=True, unique=True)

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return 'Tag<%d:%s>' % (self.id, self.name)


class DocTags(Model):
    """A tag which can be placed on a document"""
    id = Column('id', Integer(), primary_key=True)
    doc_id = Column('doc_id', Integer(), ForeignKey(Document.id), nullable=False, index=True)
    tag_id = Column('tag_id', Integer(), ForeignKey(Tag.id), nullable=False, index=True)

    unique_doc_tag = UniqueConstraint('doc_id', 'tag_id')

    doc = relationship(Document, uselist=False, backref='tags')
    tag = relationship(Tag, uselist=False)

    def __repr__(self):
        return 'DocTag<%d:%d>' % (self.doc_id, self.tag_id)


class DocSegment(Model):
    """Part of a document split out by OCR"""
    id = Column('id', Integer(), primary_key=True)
    parent_id = Column('parent_id', Integer(), ForeignKey(id), nullable=True, index=True)

    doc_id = Column('doc_id', Integer(), ForeignKey(Document.id), nullable=False, index=True)
    page = Column('page', Integer(), nullable=False)

    # row and col are inside parent, or page if parent is null
    row = Column('row', Integer(), nullable=False)
    col = Column('col', Integer(), nullable=False)

    x1 = Column('x1', Integer(), nullable=False)
    y1 = Column('y1', Integer(), nullable=False)
    x2 = Column('x2', Integer(), nullable=False)
    y2 = Column('y2', Integer(), nullable=False)

    unique_segment = UniqueConstraint('doc_id', 'page', 'x1', 'x2', 'y1', 'y2')

    ocrtext = Column('ocrtext', Text(), nullable=True, index=True)

    # This is not the same as the number of reviews - this includes reviews
    # where the user decided to skip the field.
    viewcount = Column('viewcount', Integer(), nullable=False, index=True, default=0)

    doc = relationship(Document, uselist=False, backref='segments')
    children = relationship('DocSegment', backref=backref('parent', remote_side=[id]))

    @property
    def usertext(self):
        q = app.dbobj.session\
                     .query(DocSegmentReview)\
                     .filter(DocSegmentReview.segment_id == self.id)\
                     .order_by(DocSegmentReview.rev.desc())
        return q.first()

    @property
    def besttext(self):
        return (self.usertext or self.ocrtext or '')

    @property
    def location(self):
        return (self.x1, self.y1, self.x2, self.y2)

    def __repr__(self):
        return 'DocSegment<%d:(%d,%d,%d,%d)>' % (self.doc_id, self.x1, self.y1, self.x2, self.y2)


class User(Model):
    """A user who does reviews"""
    id = Column('id', Integer(), primary_key=True)
    name = Column('name', Text(), nullable=False, unique=True)
    pw_hash = Column('pw_hash', Text(), nullable=False)

    def __repr__(self):
        return 'User<%d:%s>' % (self.id, self.name)


class DocSegmentReview(Model):
    """A review of the text in a document segment"""
    id = Column('id', Integer(), primary_key=True)
    segment_id = Column('segment_id', Integer(), ForeignKey(DocSegment.id), nullable=False)
    rev = Column('rev', Integer(), nullable=False, index=True)
    timestamp = Column('timestamp', DateTime(), nullable=False)

    user_id = Column('user_id', Integer(), ForeignKey(User.id), nullable=False)
    text = Column('text', Text(), nullable=False)

    unique_review = UniqueConstraint('segment_id', 'rev')

    user = relationship(User, uselist=False, backref='reviews')
    segment = relationship(DocSegment, uselist=False, backref='reviews')

    def __repr__(self):
        return 'DocSegmentReview<%d:seg %d:no %d>' % (self.id, self.segment_id, self.rev)
