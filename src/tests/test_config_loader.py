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

from ensembl.production.handover.config import ComparaDispatchConfig


class TestHOConfigLoader(unittest.TestCase):

    def test_config_load(self):
        # DuplicateComparaMemberXref was not implemented at this point
        config = ComparaDispatchConfig.load_config('104')
        self.assertNotIn('', config.keys())
        # DuplicateComparaMemberXref was not implemented at this point
        config = ComparaDispatchConfig.load_config('106')
        self.assertIn('DuplicateComparaMemberXref', config.keys())

        with self.assertWarns(Warning):
            config = ComparaDispatchConfig.load_config('5000')
            # Load main instead
            self.assertIn('SpeciesCommonName', config.keys())