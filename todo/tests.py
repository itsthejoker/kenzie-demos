# run with: pytest tests.py --disable-pytest-warnings -v
# the warnings are about various flask packages that are about to break
# compatibility with python 3.8.

import os
from unittest.mock import patch
from unittest.mock import MagicMock
from collections import OrderedDict

import pytest
from tinydb import TinyDB, Query

from main import _create_record
from main import db as main_db
from main import message_base
from main import success_state
from main import error_state
from main import validate_date
from main import _get_next_id
from main import _create_record

def test_message_base():
    result = message_base(None)
    assert type(result) == dict
    assert result.get('server_time') is not None
    assert result.get('data') == []
    assert len(result.keys()) == 2


def test_message_base_with_data():
    result = message_base(['hello'])
    assert type(result) == dict
    assert result.get('data') == ['hello']


def test_success_state():
    r = success_state('test')
    assert type(r) == dict
    assert len(r.keys()) == 4
    assert r['message'] == 'test'
    assert r['status'] == 'success'


def test_error_state():
    r = error_state('asdf')
    assert type(r) == dict
    assert len(r.keys()) == 4
    assert r['message'] == 'asdf'
    assert r['status'] == 'error'


def test_validate_date():
    # normal operation
    r = validate_date('a', extra_obj={'a': '2018'})
    assert r is None
    # just plain bad input
    r = validate_date('a', extra_obj={'a': 'asdf'})
    assert type(r) == dict
    assert r['message'] == 'Invalid date received - please use ISO8601!'
    # this person can't calendar
    r = validate_date('a', extra_obj={'a': '2018-31-10'})
    assert type(r) == dict
    assert r['message'] == 'Invalid date received - please use ISO8601!'


def test_get_next_id():
    if os.path.exists('test_db.json'):
        os.remove('test_db.json')
    test_db = TinyDB('test_db.json')
    r = _get_next_id(test_db)
    assert r == 0
    r = _get_next_id(test_db)
    r = _get_next_id(test_db)
    assert r == 2

    os.remove('test_db.json')
    test_db = TinyDB('test_db.json')
    r = _get_next_id(test_db)
    assert r == 0


@patch('main._get_next_id', return_value=0)
def test_create_record(a):
    from main import post_parser
    # your mother was a hamster and your father smelt of elderberries
    post_parser.parse_args = MagicMock()

    if os.path.exists('test_db.json'):
        os.remove('test_db.json')
    test_db = TinyDB('test_db.json')
    r = _create_record({'title': 'snarfleblat'}, db=test_db)
    assert r['data']['t_id'] == 0
    assert r['message'] == 'Created new todo entry! Record ID: 0'
