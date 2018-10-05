import json
from logging.config import dictConfig

import arrow
import flask
from flask import make_response
from flask import redirect
from flask_restful import Api
from flask_restful import Resource
from flask_restful import reqparse
from tinydb import Query, TinyDB

dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] %(levelname)s | %(funcName)s: %(message)s',
    }},
    'handlers': {'wsgi': {
        'class': 'logging.StreamHandler',
        'stream': 'ext://flask.logging.wsgi_errors_stream',
        'formatter': 'default'
    }},
    'root': {
        'level': 'DEBUG',
        'handlers': ['wsgi']
    }
})

app = flask.Flask(__name__)
api = Api(app)
db = TinyDB('db.json')

# Separated out by for clarity and ease of readability
post_parser = reqparse.RequestParser()
post_parser.add_argument(
    'title', type=str, required=True, help='Must have a title for your todo!'
)
post_parser.add_argument(
    'due_date', type=str, required=False, help=(
        'Set the date that your todo is due. Takes ISO8601-formatted dates,'
        ' because that is the only correct way to format a date. Example: '
        '2018-10-04'
    )
)
post_parser.add_argument(
    'completed', type=bool, required=False, help=(
        'True or false; is your todo done?'
    )
)

put_parser = reqparse.RequestParser()
put_parser.add_argument(
    'title', type=str, required=False, help='Update the title of a todo!'
)
put_parser.add_argument(
    'due_date', type=str, required=False, help=(
        'Update the date that your todo should be completed. Takes ISO8601-'
        'formatted dates, because that is the only correct way to format '
        'dates. Example: 2018-10-04'
    )
)
put_parser.add_argument(
    'completed', type=bool, required=False, help=(
        'True or false; is your todo done?'
    )
)

delete_parser = reqparse.RequestParser()
delete_parser.add_argument(
    'dry_run', type=bool, required=False, help=(
        'A boolean that simulates the delete process without data loss.'
    )
)


@app.errorhandler(404)
def page_not_found(e):
    """
    Redirect everything that we don't recognize to this url, because I am a
    mean human.

    Arguments:
        e {exception} -- literally any page request that would normally 404

    Returns:
        redirect -- sends the requester off to a land they didn't want
    """

    return redirect(
        "https://us.123rf.com/450wm/sean824/sean8241506/sean824150600032/41018523-go-away.jpg?ver=6",  # noqa: E501
        code=302
    )


def message_base(data):
    """
    Is this necessary? Absolutely not. Is it something that _could_ be useful?
    Yeah, probably. This is the information we want to return in all responses,
    success, failure, or otherwise.

    Arguments:
        data {literally anything, but prefer dict} -- any extra information
            that should be included in the response. A dict is probably best,
            but it should be in the final format that the end user will see
            it in.

    Returns:
        dict -- the information for a json response that should always be
            included.
    """

    return {
        'server_time': arrow.utcnow().for_json(),
        'data': data if data else []
    }


@api.representation('application/json')
def output_json(data, code, headers=None):
    """
    Intercept all those lame responses from reqparse and stuff them into our
    reponse format but let everything else pass normally. This is entirely
    for looks and not important to the normal functioning of the application
    in the slightest.

    Arguments:
        data {dict} -- the error object that comes in from Flask
        code {exception} -- information, if any, about what triggered the
            response

    Keyword Arguments:
        headers {[type]} -- [description] (default: {None})

    Returns:
        [type] -- [description]
    """

    # intercept those lame responses from reqparse and stuff them into our
    # response format but let everything else pass normally
    if data is not None:
        if type(data.get('message')) == dict:
            result = error_state('Validation failure!', data.get('message'))
        else:
            result = data
    else:
        result = None
    resp = make_response(json.dumps(result), code)
    resp.headers.extend(headers or {})
    return resp


def success_state(message, data=None):
    """
    Create a json response object for a successful call.

    Arguments:
        message {str} -- the message you want to return

    Keyword Arguments:
        data {any} -- literally any data you want to send back. Will be
            attached to the `data` key. (default: {None})

    Returns:
        dict -- a full success response.
    """

    resp = {
        'status': 'success',
        'message': message,
    }
    resp.update(message_base(data))
    return resp


def error_state(message, data=None):
    """
    Create a json response object for a call which ends in an error state, like
    South Dakota.

    Arguments:
        message {str} -- the message you want to return

    Keyword Arguments:
        data {any} -- literally any data you want to send back. Will be
            attached to the `data` key. (default: {None})

    Returns:
        dict -- a full success response.
    """

    resp = {
        'status': 'error',
        'message': message,
    }
    resp.update(message_base(data))
    return resp


def validate_date(field, extra_obj=None):
    """
    Take any given field that could be passed in on the request and verify that
    it's a valid date. If it's not, then return a generic response message.

    Arguments:
        field {str} -- the name of the field to check

    Returns:
        None -- on success, we modify the request itself and on failure we
            return an error state.
    """
    # need to abstract away from flask in order to adequately test this.
    if not extra_obj:
        form = flask.request.form
    else:
        form = extra_obj

    try:
        form[field] = arrow.get(
            form[field]
        )
    except (arrow.parser.ParserError, ValueError):
        return error_state('Invalid date received - please use ISO8601!')


def _get_next_id(db=db):
    """
    Get a unique ID for the next record from the DB. This is kind of
    (read: super) hacky and should never be used for production anything,
    but it was a fun exercise. Don't mind the scope shadowing -- it's there
    so we can test.

    Returns:
        int -- the integer that will be used when the next todo is created.
    """

    result = db.search(Query().name == 'super special counting key')
    if not result:
        app.logger.debug(
            'Super special counting key not found -- creating!'
        )
        db.insert({'name': 'super special counting key', 'count': 0})
    # this is a low-traffic application. Just pull the count again because
    # it's easier.
    result = db.search(Query().name == 'super special counting key')
    # increment the ID number every time we call this function.
    app.logger.debug('current count: {}'.format(result[0].get('count')))
    db.update(
        {'count': int(result[0].get('count'))+1},
        Query().name == 'super special counting key'
    )
    return result[0].get('count')


class ToDo(Resource):

    def _update_record(self, todo_id):
        try:
            todo_id = int(todo_id)
        except ValueError:
            return error_state('Must have an integer as the todo ID!')

        put_parser.parse_args()
        existing_record = db.search(Query().t_id == todo_id)

        if len(existing_record) == 0:
            return error_state('No records found with ID {}'.format(todo_id))
        else:
            # we assume that we're only going to pull one record here.
            existing_record = existing_record[0]

        # control which fields the user can update -- don't want them
        # overwriting things they shouldn't have access to
        editable_fields = [
            'title',
            'due_date',
            'completed',
        ]
        if flask.request.form.get('due_date') is not None:
            # This edits the actual request, so we don't have to worry about
            # managing the returns. Any return is an error.
            result = validate_date('due_date')
            if result:
                return result

        for field in editable_fields:
            f = flask.request.form.get(field)
            existing_record[field] = f if f else existing_record[field]
        existing_record['last_updated'] = arrow.utcnow().for_json()
        if (
            existing_record.get('completed') is True and
            existing_record.get('completed_date') is None
        ):
            existing_record['completed_date'] = arrow.utcnow().for_json()

        db.update(existing_record, Query().t_id == todo_id)
        return success_state(
            'Updated information for record ID {}'.format(todo_id),
            existing_record
        )

    def _retrieve_record(self, todo_id):
        # If '/todo/all' is requested with a GET request, then pull all records
        # and return everything.
        if todo_id == 'all':
            result = db.search(Query().t_id >= 0)
            if len(result) > 0:
                return success_state(
                    'Retrieved all records available.', result
                )
            else:
                return error_state('No records found.')

        # Nothing should be passed in, so we'll just make sure it's an integer
        # and then go from there since there's nothing to parse and check.
        try:
            todo_id = int(todo_id)
        except ValueError:
            return error_state('Must have an integer as the todo ID!')

        result = db.search(Query().t_id == todo_id)
        if len(result) == 0:
            return error_state('No todo found with that ID.')
        return success_state('Requested record(s) found.', result)

    def _delete_record(self, todo_id):
        try:
            todo_id = int(todo_id)
        except ValueError:
            return error_state('Must have an integer as the todo ID!')
        delete_parser.parse_args()
        result = db.search(Query().t_id == todo_id)
        if len(result) == 0:
            return error_state('No records found with ID {}'.format(todo_id))
        db.remove(Query().t_id == todo_id)
        return success_state('Record ID {} deleted.'.format(todo_id))

    def put(self, todo_id):
        """
        Abstracted logic away for testing purposes.
        """
        return self._update_record(todo_id)

    def get(self, todo_id):
        """
        Abstracted logic away for testing purposes.
        """
        return self._retrieve_record(todo_id)

    def delete(self, todo_id):
        """
        Abstracted logic away for testing purposes.
        """
        return self._delete_record(todo_id)


def _create_record(form, db=db):
    post_parser.parse_args()
    new_record = {
        'title': None,
        'creation_date': arrow.utcnow().for_json(),
        'last_updated': arrow.utcnow().for_json(),
        'due_date': None,
        'completed': False,
        'completion_date': None,
        't_id': _get_next_id()
    }
    editable_fields = [
        'title',
        'due_date',
        'completed',
    ]
    for field in editable_fields:
        f = form.get(field)
        new_record[field] = f if f else new_record[field]
    if new_record['completed'] is True:
        new_record['completed_date'] = arrow.utcnow().for_json()
    db.insert(new_record)
    return success_state(
        'Created new todo entry! Record ID: {}'.format(new_record['t_id']),
        {'t_id': new_record['t_id']}
    )


@app.route('/todos', methods=['POST'])
def todos():
    """
    This doesn't need to be a class because it only takes in one method.
    Creates a new todo item with the following fields:

    * Title (required)
    * Creation date
    * Last updated date
    * Due date
    * Completed (true/false)
    * Completion date
    * Record ID

    The only field that should be passed here is 'title' -- everything else
    will either go through the /todo endpoint or be automatically generated.

    Example:
        requests.post('http://localhost:5000/todos, data={'title': 'Snarf'})

    Returns:
        dict -- {'status': 'success'}
        dict -- {'status': 'error', 'message': 'the sky is blue'}
    """

    return flask.jsonify(_create_record(flask.request.form))


if __name__ == '__main__':
    app.logger.info('Starting!')
    api.add_resource(ToDo, '/todo/<string:todo_id>')
    app.run()
