import logging

logger = logging.getLogger(__name__)

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

class PhotoAppInterface:
    def __init__(self, options = None):
        pass

    def take_photo(self, meta = None, output = None, post_process = None):
        """Take the photo"""
        pass

class CallRpicamStill(PhotoAppInterface):
    def __init__(self, options = None):
        self.options = options

    def take_photo(self, meta = 'unset', output = None, post_process = None):
        logger.debug('call_rpicam_app %s', meta)

        import subprocess

        job = ['/usr/bin/rpicam-still']
        job.append('-o')
        job.append(output)
        job.append('-n')
        job.append('--verbose=0')
        
        if 'index' in self.options:
            job.append('--camera={}'.format(self.options['index']))
        else:
            job.append('--camera=0')

        logger.debug('running job = %s', job)
        result = subprocess.call(job)
        logger.info('CallRpicamStill::take_photo rpicam-still code %s', result)

        if post_process is not None and callable(post_process):
            post_process()

