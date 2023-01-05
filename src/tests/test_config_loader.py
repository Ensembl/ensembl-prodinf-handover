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
from pathlib import Path
import pkg_resources

from ensembl.production.handover.config import ComparaDispatchConfig, HandoverConfig

class TestHOConfigLoader(unittest.TestCase):

    def test_config_load_104(self):
        # DuplicateComparaMemberXref was not implemented at this point
        config = ComparaDispatchConfig.load_config('104')
        self.assertIn('homo_sapiens', config)
        self.assertIn('anopheles_gambiae', config)
        self.assertIn('zea_mays', config)

    def test_config_load_106(self):
        # DuplicateComparaMemberXref was not implemented at this point
        config = ComparaDispatchConfig.load_config('106')
        self.assertIn('homo_sapiens', config)
        self.assertIn('anopheles_gambiae', config)
        self.assertIn('zea_mays', config)

    def test_config_load_not_exists(self):
        config = ComparaDispatchConfig.load_config('5000')
        # Load main instead
        self.assertFalse(config)

class TestAPPVersion(unittest.TestCase):

    def test_config_app_version(self):
        
        version = pkg_resources.require("handover")[0].version
        with open(Path(__file__).parent.parent.parent / 'VERSION') as f:
            version_file = f.read().strip('\n')
        
        version_config = HandoverConfig.APP_VERSION
        self.assertEqual(version, version_config)
        self.assertEqual(version, version_file)
        self.assertEqual(version_file, version_config )

