# -*- coding: utf-8 -*-
"""
Tests for shikin site
"""
import os
import shikin
import tempfile
import pytest


@pytest.fixture
def client(request):
    db_fd, shikin.app.config['DATABASE'] = tempfile.mkstemp()
    client = shikin.app.test_client()
    with shikin.app.app_context():
        shikin.init_db()

    def teardown():
        """Get rid of the database again after each test."""
        os.close(db_fd)
        os.unlink(shikin.app.config['DATABASE'])
    request.addfinalizer(teardown)
    return client

# TODO: some tests :)
