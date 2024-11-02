import os
import pickle

user_dir = '.solar-times'
local_config = 'config.db'

class Store:
    def __init__(self):
        homedir = os.environ['HOME']
        config_dir = os.path.join(homedir, user_dir)
        if os.path.exists(config_dir):
            if not os.path.isdir(config_dir):
                raise Exception('local user config exists but is not directory: {}'.
                                format(config_dir))
        else:
            try:
                os.mkdir(config_dir)
            except Exception as e:
                raise Exception('cannot make user config directory: {}'.format(e))

        self.db = os.path.join(homedir, user_dir, local_config)

    def save(self, data):
        with open(self.db, 'wb+') as handle:
            pickle.dump(data, handle, protocol=pickle.HIGHEST_PROTOCOL)

    def load(self):
        try:
            with open(self.db, 'rb') as handle:
                db = pickle.load(handle)
                return db
        except Exception:
            return None
