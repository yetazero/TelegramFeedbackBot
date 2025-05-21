import configparser
import os
import logging

class ConfigManager:
    def __init__(self, config_file="config.ini"):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self._initialize_config()

    def _initialize_config(self):
        if not os.path.exists(self.config_file):
            self.config['DEFAULT'] = {'admin_id': '', 'token': '', 'cooldown': '0'}
            self.save_config()
        self.config.read(self.config_file)

    def get_config(self, key, section='DEFAULT', fallback=''):
        return self.config.get(section, key, fallback=fallback)

    def set_config(self, key, value, section='DEFAULT'):
        if section not in self.config:
            self.config[section] = {}
        self.config[section][key] = str(value)

    def save_config(self):
        try:
            with open(self.config_file, 'w') as configfile:
                self.config.write(configfile)
        except Exception as e:
            logging.error(f"Failed to save configuration: {e}")