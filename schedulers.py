import json
import logging
import urllib.parse
import urllib.request
import uuid

from datetime import date
from datetime import datetime

logger = logging.getLogger(__name__)

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

def photo_all(meta = 'unset', config = None, s = None, action = None):
    logger.debug('coordinator %s', meta)

    if config is None:
        raise Exception("must provide a config object")
    if s is None:
        raise Exception("must provide a scheduler")
    #if action is None or not callable(action):
    if action is None:
        raise Exception("must provide a callable action")

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

                s.enter(diff + 1, 1, action,
                        kwargs = {'meta': 'calling action {} at {}'.format(t, times[t]),
                                  'filename': filename,
                                  'post_process': post_process(correlation_id, t,
                                                               'next_frame', next_frame)})
                next_frame = next_frame + 1

                if t == 'solar_noon':
                    correlation_id = uuid.uuid4()
                    logger.debug('%s scheduled noon %s frame %s for delay of %s',
                                 correlation_id, t, next_noon_frame, diff)
                    frame = config['directory'] + config['format'].format(next_noon_frame)
                    s.enter(diff + 1, 1, action,
                            kwargs = {
                                'meta': 'calling action at noon {} at {}'.format(t, times[t]),
                                'filename': frame,
                                'post_process': post_process(correlation_id, t,
                                                             'next_noon_frame', next_noon_frame)})
                    next_noon_frame = next_noon_frame + 1
        except Exception as e:
            logger.error('failed on key %s - %s', t, e)
            continue