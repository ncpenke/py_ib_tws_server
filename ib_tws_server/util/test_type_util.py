from ib_tws_server.util.type_util import *
from ib_tws_server.ib_imports import *
from unittest import TestCase

class TestTypeUtil(TestCase):
    def test_find_api_type(self):
        self.assertEqual(find_sym_in_module('Contract', ibapi), ibapi.contract.Contract)

    def test_fullname(self):
        cls = find_sym_in_module('Contract', ibapi)
        self.assertEqual(cls.__name__, "Contract")
        self.assertEqual(full_class_name(cls), 'ibapi.contract.Contract')
        sample = cls()
        self.assertEqual(full_class_name(sample), 'ibapi.contract.Contract')

    def test_full_type_name_for_annotation(self):
        self.assertEqual(full_type_name_for_annotation('Contract', ibapi), 'ibapi.contract.Contract')
        self.assertEqual(full_type_name_for_annotation('list', ibapi), 'list')

    def test_find_sym_from_full_name(self):
        self.assertEqual(find_sym_from_full_name('ibapi.contract.Contract'), ibapi.contract.Contract)
    
    def test_find_sym_in_module(self):
        self.assertEqual(find_sym_in_module('FamilyCode', ibapi), ibapi.common.FamilyCode)