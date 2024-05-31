# See the NOTICE file distributed with this work for additional information
#   regarding copyright ownership.
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#       http://www.apache.org/licenses/LICENSE-2.0
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import unittest
import warnings
from pathlib import Path

import requests

from ensembl.production.handover.config import ComparaDispatchConfig, HandoverConfig
from sqlalchemy.exc import MovedIn20Warning

warnings.filterwarnings("ignore", category=MovedIn20Warning)


class TestHOConfigLoader(unittest.TestCase):

    def test_config_load_104(self):
        # compara config for fungi not existing in 104
        # ComparaDispatchConfig.divisions = ['vertebrates', 'plants', 'metazoa', 'fungi']
        with self.assertWarnsRegex(UserWarning, r'^Loading fungi compara from main.*$'):
            config = ComparaDispatchConfig.load_config('104')
        self.assertIn('homo_sapiens', config)
        self.assertIn('anopheles_gambiae', config)
        self.assertIn('zea_mays', config)

    def test_config_load_108(self):
        # All divisions now exists in compara
        config = ComparaDispatchConfig.load_config('108')
        self.assertIn('homo_sapiens', config)
        self.assertIn('anopheles_gambiae', config)
        self.assertIn('zea_mays', config)

    def test_config_load_not_exists(self):
        with self.assertWarnsRegex(UserWarning, r'^Loading metazoa compara from main.*$'):
            ComparaDispatchConfig.load_division('5000', 'metazoa')

    def test_config_load_main(self):
        with self.assertWarnsRegex(UserWarning, r'^Loading plants compara from main.*$'):
            ComparaDispatchConfig.load_division(None, 'plants')


class TestAPPVersion(unittest.TestCase):

    def test_config_app_version(self):
        try:
            from importlib.metadata import version
            version = version("handover")
            version_pkg = True
        except Exception as e:
            version = "unknown"
            version_pkg = False
        with open(Path(__file__).parents[2] / 'VERSION') as f:
            version_file = f.read()
        version_config = HandoverConfig.APP_VERSION
        print("version", version)
        print("version_config", version_config)
        print("version_file", version_file)
        if version_pkg:
            self.assertEqual(version, version_config)
            self.assertRegex(version.remove("\n", ''), version_file)
        self.assertRegex(version_config.remove("\n", ''), version_file)
