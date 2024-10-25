import json
import logging
import sched
import sys
import urllib.parse
import urllib.request
import uuid
import yaml

from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta

from pprint import pformat

# XXX holding back until figure out how to approximate rpicam-still
#from picamera2 import Picamera2
#from libcamera import controls

# Info - API parameters
#location = 'https://api.sunrise-sunset.org/json?'
#lat = 39.7592537
#lng = -105.1230315
#tzid = 'America/Denver'
#formatted = 0

# XXX Known issues
# 
# Restart: if event do or do not fire, a restart can clobber photos
# Event takes photo 1
# Writes current frame 1
# Restarts
# Next event will be photo and frame 1 as read in from config
# 
# Config should always hold the next frame, not the current frame.
# Implemented potential fix is save_config in the post processing step

# XXX take from CLI
bootstrap_config = '/home/pi/dev/python/solar-times/config.yaml'
# XXX take from CLI
logger_file = '/home/pi/dev/python/solar-times/solar.log'

logger = logging.getLogger(__name__)
logging.basicConfig(filename=logger_file, encoding='utf-8', level=logging.DEBUG,
                    format='%(levelname)s %(asctime)s : %(message)s')
logger.debug('logger initialized')

config = dict()
def load_config(filename):
    try:
        with open(filename, 'r') as f:
            data = yaml.load(f, Loader=yaml.FullLoader)
            return data
    except Exception as ex:
        logger.error('cannot load config file: %s', ex)
        sys.exit(1)

def save_config(config, filename):
    try:
        with open(filename, 'w') as f:
            yaml.dump(config, f)
    except Exception as ex:
        logger.error('cannot save config file: %s', ex)
        sys.exit(1)

def get_times(location = '', day = date.today(), lat = 0, lng = 0, tzid = '', formatted = 0):
    params = {
        'lat': lat,
        'lng': lng,
        'date': day.__str__(),
        'tzid': tzid,
        'formatted': formatted
    }

    endpoint = location + urllib.parse.urlencode(params)

    logger.info('calling api endpoint %s for times', endpoint)
    contents = urllib.request.urlopen(endpoint)
    if contents.status != 200:
        # XXX type the exception
        raise Exception('api called failed, endpoint {} status {}'.format(endpoint,
                                                                          contents.status))

    if contents.headers['content-type'] != 'application/json':
        raise Exception("unsupported content-type {} want 'application/json".format(
               contents.headers['content-type']))

    data = contents.read()
    times = json.loads(data)

    logger.debug('results: %s', times)
    return times['results']

# XXX update
#    logging
#    post process call
#    proper library usage
#def take_pic(meta = 'unset', filename = ''):
#    print(meta)
#    with Picamera2() as camera:
#        pprint(camera.sensor_modes)
#
#        camera_config = camera.create_still_configuration(main={"size":(4608, 2592)})
#        camera.configure(camera_config)
#        camera.set_controls({"AfMode": controls.AfModeEnum.Continuous})
#        camera.start()
#
#        camera.capture_file(filename)
#        camera.stop()

def call_rpicam_app(meta = 'unset', filename = '', post_process = None):
    logger.debug('call_rpicam_app %s', meta)

    import subprocess

    result = subprocess.call(["/usr/bin/rpicam-still", "-o", filename, "-n", "--verbose=0"])
    logger.info('call_rpicam_app rpicam-still code %s', result)

    if post_process is not None and callable(post_process):
        post_process()

def coordinate(meta = 'unset', s = None):
    logger.debug('coordinator %s', meta)

    try:
        times = get_times(config['location'], date.today(), config['latitude'], config['longitude'],
                          config['tzid'], config['is_formatted'])
    except Exception as e:
        logger.error('cannot get times from api', e)
        return

    # don't need the day_length
    try:
        del times['day_length']
    except KeyError as e:
        # ignore
        ...
    sorted_times = dict(sorted(times.items(), key= lambda item: item[1]))

    def post_process(correlation_id, key, frame_type, frame):
        logger.debug('%s post_process for %s type %s frame %s',
                     correlation_id, key, frame_type, frame)
        def process():
            logger.debug('%s process for %s type %s frame %s',
                         correlation_id, key, frame_type, frame)

            # store the *next* expected frame
            config[frame_type] = frame + 1

            logger.debug('%s process saving configuration %s', correlation_id, bootstrap_config)
            save_config(config, bootstrap_config)
        return process

    # these are the *next* frames in the sequence
    next_frame = config['next_frame']
    next_noon_frame = config['next_noon_frame']
    for t in sorted_times.keys():
        try:
            iso = datetime.fromisoformat(times[t])
            if iso.timestamp() < datetime.now().timestamp():
                logger.debug('found %s with time %s is in the past', t, times[t])
            else:
                name = t + '-' + config['format'].format(next_frame)
                filename = config['directory'] + name
                now = datetime.now()
                diff = iso.timestamp() - datetime.now().timestamp()
                correlation_id = uuid.uuid4()
                logger.debug('%s scheduled %s frame %s for delay of %s',
                             correlation_id, t, next_frame, diff)

                # XXX rpicamp-still takes better pictures, unsure what settings differ
                #s.enter(diff, 1, take_pic,
                #        kwargs = {'meta': 'taking photo of {} at {}'.format(t, times[t]),
                #                  'frame': config['frame']})

                s.enter(diff + 1, 1, call_rpicam_app,
                        kwargs = {'meta': 'taking rpicam-still of {} at {}'.format(t, times[t]),
                                  'filename': filename,
                                  'post_process': post_process(correlation_id, t,
                                                               'next_frame', next_frame)})
                next_frame = next_frame + 1

                if t == 'solar_noon':
                    correlation_id = uuid.uuid4()
                    logger.debug('%s scheduled noon %s frame %s for delay of %s',
                                 correlation_id, t, next_noon_frame, diff)
                    frame = config['directory'] + config['format'].format(next_noon_frame)
                    s.enter(diff + 1, 1, call_rpicam_app,
                            kwargs = {
                                'meta': 'taking rpicam-still of noon {} at {}'.format(t, times[t]),
                                'filename': frame,
                                'post_process': post_process(correlation_id, t,
                                                             'next_noon_frame', next_noon_frame)})
                    next_noon_frame = next_noon_frame + 1
        except Exception as e:
            logger.error('failed on key %s - %s', t, e)
            continue

def next_coordinate(meta = 'unset', s = None):
    logger.debug('next_coordinate %s', meta)

    today = date.today()
    tomorrow = today + timedelta(days=1)

    t = config['reset_time']
    hour = (lambda: 1, lambda: t[0])[len(t) >= 1 and t[0] <= 11]()
    minute = (lambda: 0, lambda: t[1])[len(t) >= 2 and t[1] <= 59]()
    second = (lambda: 0, lambda: t[2])[len(t) >= 3 and t[2] <= 59]()
    tomorrow_morning = datetime.combine(tomorrow,
                                        time(hour=hour, minute=minute, second=second))

    next_morning = tomorrow_morning.timestamp() - datetime.now().timestamp()
    logger.debug('next coorination attempt at %s', next_morning)
    s.enter(next_morning, 1, coordinate,
            kwargs = {'meta': 'next morning {}'.format(next_morning), 's': s})

def keepalive(meta = 'unset', s = None):
    logger.debug('keepalive %s', meta)

    logger.debug('queue depth %s', len(s.queue))
    logger.debug('queue %s', pformat(s.queue))
    s.enter(config['keepalive'], 1, keepalive, kwargs = {'meta': 'keepalive run', 's': s})

def main():
    # XXX take from the command line
    global config
    config = load_config(bootstrap_config)
    logger.debug('main configuration set to %s', config)
    s = sched.scheduler()

    next_coordinate(meta = 'running coordination setup on initialization', s = s)
    coordinate(meta = 'initial cooridination run on startup', s = s)

    s.enter(1, 1, keepalive, kwargs = {'meta': 'keepalive run - init', 's': s})
    s.run()

if __name__ == "__main__":
    main()
