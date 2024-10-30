import logging
import sched
import sys
import yaml

from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta

from pprint import pformat

from schedulers import photo_all

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

    photo_all('running scheduled job', config, s, call_rpicam_app)

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

    scheduler(meta = 'running scheduler setup on initialization', s = s)
    s.enter(1, 1, keepalive, kwargs = {'meta': 'keepalive run - init', 's': s})
    s.run()

if __name__ == "__main__":
    main()
