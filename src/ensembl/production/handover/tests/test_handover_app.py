# .. See the NOTICE file distributed with this work for additional information
#    regarding copyright ownership.
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#        http://www.apache.org/licenses/LICENSE-2.0
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

import unittest
from ensembl.production.handover.app.main import valid_handover
from ensembl.production.handover.celery_app.utils import parse_db_infos
import ensembl.production.handover.celery_app.utils as ut

class TestHandover(unittest.TestCase):
    def test_valid_handover_valid(self):
        release = '101'
        valid_uris = [
            'mysql://ensro@mysql-ens-vertannot-staging:4573/ensembl_compara_fungi_48_101',
            'mysql://ensro@mysql-ens-vertannot-staging:4573/ensembl_compara_metazoa_48_101',
            'mysql://ensro@mysql-ens-vertannot-staging:4573/ensembl_compara_pan_homology_48_101',
            'mysql://ensro@mysql-ens-vertannot-staging:4573/ensembl_compara_plants_48_101',
            'mysql://ensro@mysql-ens-vertannot-staging:4573/ensembl_compara_protists_48_101',
            'mysql://ensro@mysql-ens-vertannot-staging:4573/ensembl_compara_bacteria_48_101',
            'mysql://ensro@mysql-ens-vertannot-staging:4573/ensembl_compara_101',
            'mysql://ensro@mysql-ens-vertannot-staging:4573/bacteria_0_collection_core_48_101_1',
            'mysql://ensro@mysql-ens-vertannot-staging:4573/bacteria_100_collection_core_48_101_1',
            'mysql://ensro@mysql-ens-vertannot-staging:4573/bacteria_101_collection_core_48_101_1',
            'mysql://ensro@mysql-ens-vertannot-staging:4573/fungi_ascomycota1_collection_core_48_101_1',
            'mysql://ensro@mysql-ens-vertannot-staging:4573/fungi_ascomycota2_collection_core_48_101_1',
            'mysql://ensro@mysql-ens-vertannot-staging:4573/capra_hircus_core_101_1',
            'mysql://ensro@mysql-ens-vertannot-staging:4573/ovis_aries_core_101_31',
            'mysql://ensro@mysql-ens-vertannot-staging:4573/capra_hircus_core_101_1',
        ]
        for uri in valid_uris:
            doc = {'_source': {'params': {'src_uri': uri}}}
            try:
                self.assertTrue(valid_handover(doc, release))
            except AssertionError as e:
                raise AssertionError('Invalid Uri: %s' % uri) from e

    def test_valid_handover_invalid(self):
        release = '101'
        invalid_uris = [
            'mysql://ensro@mysql-ens-vertannot-staging:4573/zonotrichia_albicollis_rnaseq_96_101',
            'mysql://ensro@mysql-ens-vertannot-staging:4573/zonotrichia_albicollis_otherfeatures_96_101',
            'mysql://ensro@mysql-ens-vertannot-staging:4573/zonotrichia_albicollis_core_96_101',
        ]
        for uri in invalid_uris:
            doc = {'_source': {'params': {'src_uri': uri}}}
            self.assertFalse(valid_handover(doc, release))
    
    def test_valid_core_database(self):
        expect_db_type='core'
        dbname='zonotrichia_albicollis_core_96_101'  
        db_prefix, db_type, assembly = parse_db_infos(dbname)
        self.assertTrue(expect_db_type, db_type)
          
class ParseDbInfosTest(unittest.TestCase):
    def test_accepted_species_patterns(self):
        names = (
            'homo_sapiens_cdna_100_38',
            'homo_sapiens_core_100_38',
            'homo_sapiens_funcgen_100_38',
            'homo_sapiens_otherfeatures_100_38',
            'homo_sapiens_rnaseq_100_38',
            'homo_sapiens_variation_100_38',
            'bacteria_0_collection_core_47_100_1',
            'bacteria_100_collection_core_47_100_1',
            'bacteria_101_collection_core_47_100_1',
            'fungi_ascomycota1_collection_core_47_100_1',
            'fungi_ascomycota2_collection_core_47_100_1',
            'hordeum_vulgare_core_47_100_3',
            'hordeum_vulgare_funcgen_47_100_3',
            'hordeum_vulgare_otherfeatures_47_100_3',
            'hordeum_vulgare_variation_47_100_3',
            'protists_alveolata1_collection_core_47_100_1',
            'protists_amoebozoa1_collection_core_47_100_1',
            'protists_apusozoa1_collection_core_47_100_1',
            'protists_choanoflagellida1_collection_core_47_100_1',
            'protists_cryptophyta1_collection_core_47_100_1',
            'protists_euglenozoa1_collection_core_47_100_1',
            'anas_platyrhynchos_platyrhynchos_core_100_1',
            'canis_lupus_familiarisbasenji_core_100_11',
        )
        parsed_names = (
            ('homo_sapiens', 'cdna',  '38'),
            ('homo_sapiens', 'core',  '38'),
            ('homo_sapiens', 'funcgen',  '38'),
            ('homo_sapiens', 'otherfeatures', '38'),
            ('homo_sapiens', 'rnaseq',  '38'),
            ('homo_sapiens', 'variation', '38'),
            ('bacteria_0_collection', 'core',  '1'),
            ('bacteria_100_collection', 'core',  '1'),
            ('bacteria_101_collection', 'core',  '1'),
            ('fungi_ascomycota1_collection', 'core',  '1'),
            ('fungi_ascomycota2_collection', 'core', '1'),
            ('hordeum_vulgare', 'core',  '3'),
            ('hordeum_vulgare', 'funcgen',  '3'),
            ('hordeum_vulgare', 'otherfeatures',  '3'),
            ('hordeum_vulgare', 'variation',  '3'),
            ('protists_alveolata1_collection', 'core',  '1'),
            ('protists_amoebozoa1_collection', 'core',  '1'),
            ('protists_apusozoa1_collection', 'core',  '1'),
            ('protists_choanoflagellida1_collection', 'core','1'),
            ('protists_cryptophyta1_collection', 'core', '1'),
            ('protists_euglenozoa1_collection', 'core','1'),
            ('anas_platyrhynchos_platyrhynchos', 'core', '1'),
            ('canis_lupus_familiarisbasenji','core',  '11'),
        )
        for parsed_name, database_name in zip(parsed_names, names):
            self.assertEqual(parsed_name, ut.parse_db_infos(database_name))

    def test_accepted_compara_patterns(self):
        names = (
            'ensembl_compara_fungi_47_100',
            'ensembl_compara_metazoa_47_100',
            'ensembl_compara_pan_homology_47_100',
            'ensembl_compara_plants_47_100',
            'ensembl_compara_protists_47_100',
            'ensembl_compara_bacteria_47_100',
            'ensembl_compara_100'
        )
        parsed_names = (
            ('fungi', 'compara', None),
            ('metazoa', 'compara', None),
            ('pan', 'compara', None),
            ('plants', 'compara', None),
            ('protists', 'compara', None),
            ('bacteria', 'compara', None),
            ('vertebrates', 'compara', None)
        )
        for parsed_name, database_name in zip(parsed_names, names):
            self.assertEqual(parsed_name, ut.parse_db_infos(database_name))

    def test_accepted_ancestral_patterns(self):
        names = (
            'ensembl_ancestral_100',
            'ensembl_ancestral_1'
        )
        parsed = ('vertebrates', 'ancestral', None)
        for database_name in names:
            self.assertEqual(parsed, ut.parse_db_infos(database_name))

    def test_rejected_species_patterns(self):
        invalid_names = (
            'homo_sapiens_cdna_100',
            'bacteria_0_collection_47_100_1',
            'ensembl_ancestral',
            'ensembl_compara_100_grch37'
        )
        for invalid_database_name in invalid_names:
            self.assertRaises(ValueError, ut.parse_db_infos, invalid_database_name)
