import argparse
import logging
import sched
import sys
import yaml

from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta

from pprint import pformat

from schedulers import *
from apps import *

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
# 1 - direct use of picamera2 doesn't take quality photos
# X2 - scheduler needs a CLI
# X3 - config file needs a CLI
# X4 - logger file needs a CLI
# X5 - make scheduler use a configurable "scheduler" object/action
#     make a "job" to use either rpicam app or picamera2 function
#     scheduler gets rules and a job? right now scheduler works at a specific time to call
#     a function, which calls a camera app. scheduler can use a set of rules to call a cam
#     app instead.
# 6 - make scheduler work at an interval or specific times (list)
# 7 - convert to using type hints

logger = logging.getLogger(__name__)
app = None
job = None
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

def scheduler(meta = 'unset', s = None):
    logger.debug('scheduler %s', meta)

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
    s.enter(next_morning, 1, scheduler,
            kwargs = {'meta': 'next morning {}'.format(next_morning), 's': s})

    job('running scheduled job = {}'.format(job), config, s, app)

def keepalive(meta = 'unset', s = None):
    logger.debug('keepalive %s', meta)

    logger.debug('queue depth %s', len(s.queue))
    logger.debug('queue %s', pformat(s.queue))
    s.enter(config['keepalive'], 1, keepalive, kwargs = {'meta': 'keepalive run', 's': s})

def main():
    parser = argparse.ArgumentParser(description='solar-times.py: Art Project - photo scheduler')
    parser.add_argument(
            '--app',
            help='Application to interface with camera hardware. Options: rpicam-still',
            default='rpicam-still')
    parser.add_argument(
            '--log',
            help='Log file',
            default='/var/log/solar-times/solar-times.log')
    parser.add_argument(
            '--config',
            help='Configuration file',
            default='${HOME}/.solar-times/config.yaml')
    parser.add_argument(
            '--job',
            help='Job type to run with each schedule. Options: now, morning, all',
            default='now')

    args = parser.parse_args()

    logging.basicConfig(filename=args.log, encoding='utf-8', level=logging.DEBUG,
                        format='%(levelname)s %(asctime)s : %(message)s')
    logger.debug('logger initialized')

    # load config
    global config
    config = load_config(args.config)
    logger.debug('main configuration set to %s', config)

    # set app
    global app
    match args.app:
        case 'rpicam-still':
            app = CallRpicamStill(config['cam_options'])
        case _:
            print('app {} is unsupported'.format(args.app), file=sys.stderr)
            exit(1)

    # set job
    global job
    match args.job:
        case 'now':
            job = photo_now
        case 'morning':
            job = photo_morning
        case 'all':
            job = photo_all
        case _:
            print('job {} is unsupported'.format(args.job), file=sys.stderr)
            exit(1)

    s = sched.scheduler()

    scheduler(meta = 'running scheduler setup on initialization', s = s)
    s.enter(1, 1, keepalive, kwargs = {'meta': 'keepalive run - init', 's': s})
    s.run()

if __name__ == '__main__':
    main()
