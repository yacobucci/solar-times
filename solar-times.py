import json
import sched

import urllib.parse
import urllib.request

from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta

from pprint import *

from picamera2 import Picamera2
from libcamera import controls

location = 'https://api.sunrise-sunset.org/json?'

lat = 39.7592537
lng = -105.1230315
tzid = 'America/Denver'
formatted = 0

today = date.today()
tomorrow = today + timedelta(days=1)
tomorrow_morning = datetime.combine(tomorrow, time(hour=1))

print("Meta: tomorrow: {} morning: {}  Params: lat: {} lng: {} date: {} tzid: {} format: {}".format(tomorrow.__str__(), tomorrow_morning, lat, lng, today.__str__(), tzid, formatted))

params = {
        'lat': lat,
        'lng': lng,
        'date': today.__str__(),
        'tzid': tzid,
        'formatted': formatted
}

endpoint = location + urllib.parse.urlencode(params)

print(endpoint)

contents = urllib.request.urlopen(endpoint)
if contents.status != 200:
    print("I'm a failure...")
    exit(1)
else:
    print("Succeeding, for now...")

if contents.headers['content-type'] != 'application/json':
    print("Unsupported content-type")
    exit(1)

data = contents.read()
times = json.loads(data)

print(times)

#echo 'touch $(date)' | at -t $(echo 2024-10-11T19:27:51-06:00 | sed -e 's/-\([^-]*\)$//' -e 's/-//g' -e 's/T//' -e 's/://' -e 's/:/./')

def take_pic(meta = 'unset', frame = 0):
    print(meta)
    with Picamera2() as camera:
        pprint(camera.sensor_modes)

        camera_config = camera.create_still_configuration(main={"size":(4608, 2592)})
        camera.configure(camera_config)
        camera.set_controls({"AfMode": controls.AfModeEnum.Continuous})
        camera.start()
        camera.capture_file("/home/pi/Pictures/test/sched/frame{}.jpg".format(frame))
        camera.stop()

#frame = 0
frame = 1
s = sched.scheduler()

def check(meta = 'unset'):
    print(meta)
    pprint(datetime.now().timestamp())
    pprint(s.queue)

def coordinator(meta = 'unset'):
    print('coordinator {}'.format(meta))

by_morning = tomorrow_morning.timestamp() - datetime.now().timestamp()
s.enter(by_morning, 1, coordinator, kwargs = {'meta': 'next morning {}'.format(by_morning)})

s.enter(15, 1, check, kwargs = {'meta': 'from 15 seconds ago'})
for t in times['results'].keys():
    print(t)
    print(times['results'][t])
    try:
        iso = datetime.fromisoformat(times['results'][t])
        if iso.timestamp() < datetime.now().timestamp():
            print("In the past")
        else:
            now = datetime.now()
            diff = iso.timestamp() - datetime.now().timestamp()
            print("scheduled frame {} for {}".format(frame, diff))
            #s.enterabs(iso.timestamp(), 1, take_pic, kwargs = {'frame': frame})
            s.enter(diff, 1, check, kwargs = {'meta': "frame {} from timedelta: {}".format(frame, diff)})
            s.enter(diff, 1, take_pic, kwargs = {'frame': frame, 'meta': 'frame {} from timedelta: {}'.format(frame, diff)})
            frame = frame + 1
    except:
        print("failed on key {}".format(t))
        continue

#s.enter(15, 1, check, kwargs={'meta': 'enter with 15'})
#nxt = datetime.now() + timedelta(seconds=30)
#s.enterabs(int(nxt.timestamp()), 1, check, kwargs={'meta': 'enterabs with +30'})

#next_nxt = (datetime.now() + timedelta(seconds=60)).timestamp() - datetime.now().timestamp()
#print(next_nxt)
#s.enter(next_nxt, 1, check, kwargs={'meta': 'enter with +60 and goofy calc'})

s.run()
