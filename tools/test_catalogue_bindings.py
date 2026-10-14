"""Cache identity and same-site directory boundary for split catalog requests."""
import unittest
from verify_mission_readers import BrowseBindings,valid_catalogue_binding

class CatalogueBindingTests(unittest.TestCase):
 def test_split_endpoint_retains_effective_catalog_version(self):
  parser=BrowseBindings();parser.feed('<section class="browse" data-catalog="/starrail-quests/reading-catalog/" data-catalog-version="abcdef123456"></section>')
  self.assertEqual(parser.catalogues,[('/starrail-quests/reading-catalog/','abcdef123456')])
  self.assertTrue(valid_catalogue_binding(*parser.catalogues[0],'abcdef123456'))
 def test_stale_missing_or_foreign_catalog_identity_is_rejected(self):
  for endpoint,version in [('/starrail-quests/reading-catalog/','old'),('/starrail-quests/reading-catalog/',''),('/starrail-quests/reading-catalog.json?v=abcdef123456','abcdef123456'),('https://foreign.test/starrail-quests/reading-catalog/','abcdef123456'),('//foreign.test/starrail-quests/reading-catalog/','abcdef123456'),('/foreign/reading-catalog/','abcdef123456'),('/starrail-quests/reading-catalog/?v=old','abcdef123456'),('/starrail-quests/reading-catalog/#old','abcdef123456')]:
   with self.subTest(endpoint=endpoint,version=version):self.assertFalse(valid_catalogue_binding(endpoint,version,'abcdef123456'))
if __name__=='__main__':unittest.main()
