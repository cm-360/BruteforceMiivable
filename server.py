from flask import Flask, request, render_template, make_response, g
from werkzeug.middleware.proxy_fix import ProxyFix
from functools import wraps
from logging.config import dictConfig

from pyzbar.pyzbar import decode as qr_decode
from PIL import Image

from dotenv import load_dotenv

import base64
import json
import os
import re
import secrets

from jobs import JobManager, MiiJob, Part1Job, read_movable, count_total_mined


# constants
id0_regex = re.compile(r'[a-fA-F0-9]{32}')

# logging config
dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    }},
    'handlers': {'wsgi': {
        'class': 'logging.StreamHandler',
        'stream': 'ext://flask.logging.wsgi_errors_stream',
        'formatter': 'default'
    }},
    'root': {
        'level': 'INFO',
        'handlers': ['wsgi']
    }
})

# flask app
app = Flask(__name__)
app.wsgi_app = ProxyFix(
    app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
)
app.config['TEMPLATES_AUTO_RELOAD'] = True

# job manager
manager = JobManager()

# total movables mined
total_mined = 0


def check_auth(username, password):
    return username == os.getenv('ADMIN_USER', 'admin') and password == os.getenv('ADMIN_PASS', 'INSECURE')

# https://stackoverflow.com/questions/22919182/flask-http-basicauth-how-does-it-work
def login_required(f):
    @wraps(f)
    def wrapped_view(**kwargs):
        auth = request.authorization
        if not (auth and check_auth(auth.username, auth.password)):
            return ('Unauthorized', 401, {
                'WWW-Authenticate': 'Basic realm="Login Required"'
            })
        return f(**kwargs)
    return wrapped_view


# frontend routes

@app.route('/')
def page_home():
    return render_template('pages/home.html')

@app.route('/volunteer')
def page_volunteer():
    return render_template('pages/volunteer.html')

@app.route('/admin')
@login_required
def page_admin():
    return render_template('pages/admin.html')

@app.route('/js/<path:filename>')
def serve_js(filename):
    response = make_response(render_template('js/' + filename))
    response.headers.set('Content-Type', 'text/javascript')
    return response

@app.route('/get_mining_client')
def get_mining_client():
    client_filename = 'mining_client.py'
    response = make_response(render_template(client_filename))
    response.headers.set('Content-Type', 'application/octet-stream')
    response.headers.set('Content-Disposition', 'attachment', filename=client_filename)
    return response


# api routes

@app.route('/api/submit_mii_job', methods=['POST'])
def api_submit_mii_job():
    job = None
    # parse job submission
    submission = request.get_json(silent=True)
    if submission:
        job = parse_mii_job_submission(request.json)
    else:
        job = parse_mii_job_submission(request.form, mii_file=request.files['mii_file'])
    # returns error message if job json is invalid
    if type(job) is str:
        return error(job)
    # overwrite job if canceled
    status = manager.check_job_status(job.id0)
    if status == 'canceled':
        manager.delete_job(job.id0)
        status = None
    if not status:
        manager.submit_job(job)
        app.logger.info('job submitted: \t' + job.id0)
    return success({'id0': job.id0})

@app.route('/api/request_job')
def api_request_job():
    release_dead_jobs()
    miner_ip = get_request_ip()
    app.logger.info(f'{miner_ip} requests work')
    miner_name = request.args.get('name', miner_ip)
    job = manager.request_job(miner_name, miner_ip)
    if not job:
        return success()
    app.logger.info('job assigned: \t' + job.id0)
    return success(dict(job))

@app.route('/api/release_job/<id0>')
def api_release_job(id0):
    pass

@app.route('/api/check_job_status/<id0>')
def api_check_job_status(id0):
    if not is_id0(id0):
        return error('Invalid ID0')
    status = manager.check_job_status(id0)
    if not status:
        return error('Job not found', 404)
    return success({'status': status})

@app.route('/api/update_job/<id0>')
def api_update_job(id0):
    if not is_id0(id0):
        return error('Invalid ID0')
    miner_ip = get_request_ip()
    app.logger.info(f'{miner_ip} is still mining')
    result = manager.update_job(id0, miner_ip)
    if not result:
        return error('Job not found', 404)
    if type(result) == str:
        return success({'status': result})
    else:
        return success()

@app.route('/api/cancel_job/<id0>')
def api_cancel_job(id0):
    trim_canceled_jobs()
    if not is_id0(id0):
        return error('Invalid ID0')
    # TODO token check
    result = manager.cancel_job(id0)
    if not result:
        return error('Job not found', 404)
    app.logger.info('job canceled: \t' + id0)
    return success()

@app.route('/api/complete_job/<id0>', methods=['POST'])
def api_complete_job(id0):
    global total_mined
    if not is_id0(id0):
        return error('Invalid ID0')
    # TODO token check
    movable = base64.b64decode(request.json['movable'])
    if not manager.complete_job(id0, movable):
        return error('Job not found', 404)
    app.logger.info('job completed: \t' + id0)
    total_mined += 1
    return success()

@app.route('/api/check_network_stats')
def api_check_network_stats():
    return success({
        'waiting': manager.count_jobs('waiting'),
        'working': manager.count_jobs('working'),
        'miners': manager.count_miners(active_only=True),
        'totalMined': total_mined
    })

@app.route('/api/admin/list_jobs')
@login_required
def api_admin_list_jobs():
    with manager.lock:
        return success({
            'jobs': [dict(j) for j in manager.list_jobs()],
            'queue': list(manager.wait_queue)
        })

@app.route('/api/admin/list_miners')
@login_required
def api_admin_list_miners():
    with manager.lock:
        return success({
            'miners': [dict(m) for m in manager.list_miners()]
        })


# response templates

def success(data={}):
    response_json = json.dumps({
        'result': 'success',
        'data': data
    })
    return make_response(response_json, 200)

def error(message, code=400):
    response_json = json.dumps({
        'result': 'error',
        'message': message
    })
    return make_response(response_json, code)


# download movable

@app.route('/download_movable/<id0>')
def download_movable(id0):
    if not is_id0(id0):
        return error('Invalid ID0')
    movable = read_movable(id0)
    if not movable:
        return error('Movable not found', 404)
    response = make_response(movable)
    response.headers.set('Content-Type', 'application/octet-stream')
    response.headers.set('Content-Disposition', 'attachment', filename=f'movable.sed')
    return response


# cleanup routines

def release_dead_jobs():
    released = manager.release_dead_jobs()
    if released:
        app.logger.info('jobs released:')
        for id0 in released:
            app.logger.info(f'\t\t{id0}')

def trim_canceled_jobs():
    deleted = manager.trim_canceled_jobs()
    if deleted:
        app.logger.info('jobs deleted:')
        for id0 in deleted:
            app.logger.info(f'\t\t{id0}')


# helpers

def is_id0(value):
    return bool(id0_regex.fullmatch(value))

def parse_mii_job_submission(job_json, mii_file=None):
    invalid = []
    try:
        # id0
        id0 = job_json['id0']
        if not is_id0(id0):
            invalid.append('id0')
        # model
        model = job_json['model'].lower()
        if model not in ['old', 'new']:
            invalid.append('model')
        # year
        year = None
        if job_json['year']:
            try:
                year = int(job_json['year'])
                if year < 2011 or year > 2020:
                    invalid.append('year')
            except (ValueError, TypeError) as e:
                invalid.append('year')
        # mii data
        mii_data = job_json.get('mii_data')
        if mii_file:
            mii_data = process_mii_file(mii_file)
        if not mii_data:
            invalid.append('mii')
        if invalid:
            return 'invalid:' + ','.join(invalid)
        else:
            return MiiJob(id0, model, year, mii_data)
    except KeyError as e:
        return 'Missing parameter ' + str(e)
    except Exception as e:
        return str(type(e)) + str(e)

def process_mii_file(mii_file):
    filename = mii_file.filename.lower()
    raw_data = None
    # determine upload type
    if mii_file.mimetype == 'application/octet-stream' or filename.endswith('.bin'):
        raw_data = mii_file.read()
    else:
        try:
            decoded = qr_decode(Image.open(mii_file), binary=True)
            if not decoded:
                return
            raw_data = decoded[0].data
        except:
            pass
    # base64 encode
    if raw_data and len(raw_data) == 112:
        return str(base64.b64encode(raw_data), 'utf-8')

def get_request_ip():
    if request.environ.get('HTTP_X_FORWARDED_FOR') is None:
        return request.environ['REMOTE_ADDR']
    else:
        return request.environ['HTTP_X_FORWARDED_FOR']


# main

if __name__ == '__main__':
    load_dotenv()
    total_mined = count_total_mined()
    app.logger.info(f'mined {total_mined} movables previously')
    from waitress import serve
    serve(app, host=os.getenv('HOST_ADDR', '127.0.0.1'), port=os.getenv('HOST_PORT', 7799))
