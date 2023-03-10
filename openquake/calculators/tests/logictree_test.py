# -*- coding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright (C) 2015-2023 GEM Foundation
#
# OpenQuake is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OpenQuake is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with OpenQuake. If not, see <http://www.gnu.org/licenses/>.

import json
import unittest
import numpy
from openquake.baselib import general, config
from openquake.baselib.python3compat import decode
from openquake.hazardlib import contexts
from openquake.calculators.views import view, text_table
from openquake.calculators.export import export
from openquake.calculators.extract import extract
from openquake.calculators.tests import CalculatorTestCase, strip_calc_id
from openquake.qa_tests_data.logictree import (
    case_06, case_07, case_08, case_09,
    case_10, case_11, case_13, case_15, case_16, case_17,
    case_20, case_21, case_28, case_31, case_36, case_45, case_46,
    case_56, case_58, case_59, case_67, case_68, case_71, case_73,
    case_79, case_83)

ae = numpy.testing.assert_equal
aac = numpy.testing.assert_allclose


class LogicTreeTestCase(CalculatorTestCase):

    def assert_curves_ok(self, expected, test_dir, delta=None, **kw):
        kind = kw.pop('kind', '')
        self.run_calc(test_dir, 'job.ini', **kw)
        ds = self.calc.datastore
        got = (export(('hcurves/' + kind, 'csv'), ds) +
               export(('hmaps/' + kind, 'csv'), ds) +
               export(('uhs/' + kind, 'csv'), ds))
        self.assertEqual(len(expected), len(got), str(got))
        for fname, actual in zip(expected, got):
            self.assertEqualFiles('expected/%s' % fname, actual,
                                  delta=delta)
        return got

    def test_case_06(self):
        # two source model, use_rates and disagg_by_src
        self.assert_curves_ok(
            ['curve-mean.csv', 'curve-rlz0.csv', 'curve-rlz1.csv'],
            case_06.__file__)

    def test_case_07(self):
        # this is a case with 3 source models and a source ("1") belonging
        # both to source_model_1 and source_model_2
        # we are checking use_rates and disagg_by_src
        self.assert_curves_ok(
            ['hazard_curve-mean.csv',
             'hazard_curve-smltp_b1-gsimltp_b1.csv',
             'hazard_curve-smltp_b2-gsimltp_b1.csv',
             'hazard_curve-smltp_b3-gsimltp_b1.csv'],
            case_07.__file__)

        # check the weights of the sources
        info = self.calc.datastore.read_df('source_info', 'source_id')
        self.assertEqual(info.loc[b'1'].weight, 184)
        self.assertEqual(info.loc[b'2'].weight, 118)
        self.assertEqual(info.loc[b'3'].weight, 3914)

    def test_case_07_bis(self):
        # check disagg_by_source with sampling
        raise unittest.SkipTest('Not working yet')
        self.run_calc(case_07.__file__, 'sampling.ini')
        fnames = export(('hcurves', 'csv'), self.calc.datastore)
        for fname in fnames:
            self.assertEqualFiles('expected/' + strip_calc_id(fname), fname,
                                  delta=1E-5)

    def test_case_08(self):
        self.assert_curves_ok(
            ['hazard_curve-smltp_b1_b2-gsimltp_b1.csv',
             'hazard_curve-smltp_b1_b3-gsimltp_b1.csv',
             'hazard_curve-smltp_b1_b4-gsimltp_b1.csv'],
            case_08.__file__)

    def test_case_09(self):
        self.assert_curves_ok(
            ['hazard_curve-smltp_b1_b2-gsimltp_b1.csv',
             'hazard_curve-smltp_b1_b3-gsimltp_b1.csv'],
            case_09.__file__)

    def test_case_10(self):
        self.assert_curves_ok(
            ['hazard_curve-smltp_b1_b2-gsimltp_b1.csv',
             'hazard_curve-smltp_b1_b3-gsimltp_b1.csv'],
            case_10.__file__)

    def test_case_11(self):
        self.assert_curves_ok(
            ['hazard_curve-mean.csv',
             'hazard_curve-smltp_b1_b2-gsimltp_b1.csv',
             'hazard_curve-smltp_b1_b3-gsimltp_b1.csv',
             'hazard_curve-smltp_b1_b4-gsimltp_b1.csv',
             'quantile_curve-0.1.csv',
             'quantile_curve-0.9.csv'],
            case_11.__file__)

    def test_case_13(self):
        self.assert_curves_ok(
            ['hazard_curve-mean_PGA.csv', 'hazard_curve-mean_SA(0.2).csv',
             'hazard_map-mean.csv'], case_13.__file__, delta=1E-5)

        # test recomputing the hazard maps
        self.run_calc(
            case_13.__file__, 'job.ini', exports='csv',
            hazard_calculation_id=str(self.calc.datastore.calc_id),
            gsim_logic_tree_file='', source_model_logic_tree_file='')
        [fname] = export(('hmaps', 'csv'), self.calc.datastore)
        self.assertEqualFiles('expected/hazard_map-mean.csv', fname,
                              delta=1E-5)

        csv = general.gettemp(
            text_table(view('extreme_sites', self.calc.datastore)))
        self.assertEqualFiles('expected/extreme_sites.rst', csv)

        # test extract/hcurves/rlz-0, used by the npz exports
        haz = vars(extract(self.calc.datastore, 'hcurves'))
        self.assertEqual(sorted(haz), ['_extra', 'all', 'investigation_time'])
        self.assertEqual(
            haz['all'].dtype.names, ('lon', 'lat', 'depth', 'mean'))
        array = haz['all']['mean']
        self.assertEqual(array.dtype.names, ('PGA', 'SA(0.2)'))
        self.assertEqual(array['PGA'].dtype.names,
                         ('0.005', '0.007', '0.0098', '0.0137', '0.0192',
                          '0.0269', '0.0376', '0.0527', '0.0738', '0.103',
                          '0.145', '0.203', '0.284'))

        # checking sources_branches
        tbl = general.gettemp(
            text_table(view('sources_branches', self.calc.datastore),
                       ext='org'))
        self.assertEqualFiles('expected/source_branches.org', tbl)

    def test_case_15(self):
        # this is a case with both splittable and unsplittable sources
        self.assert_curves_ok('''\
hazard_curve-max-PGA.csv,
hazard_curve-mean-PGA.csv
hazard_curve-std-PGA.csv
hazard_uhs-max.csv
hazard_uhs-mean.csv
hazard_uhs-std.csv
'''.split(), case_15.__file__, delta=1E-6)

        # test UHS XML export
        fnames = [f for f in export(('uhs', 'xml'), self.calc.datastore)
                  if 'mean' in f]
        self.assertEqualFiles('expected/hazard_uhs-mean-0.01.xml', fnames[0])
        self.assertEqualFiles('expected/hazard_uhs-mean-0.1.xml', fnames[1])
        self.assertEqualFiles('expected/hazard_uhs-mean-0.2.xml', fnames[2])

        # npz exports
        [fname] = export(('hmaps', 'npz'), self.calc.datastore)
        arr = numpy.load(fname)['all']
        self.assertEqual(arr['mean'].dtype.names, ('PGA',))
        [fname] = export(('uhs', 'npz'), self.calc.datastore)
        arr = numpy.load(fname)['all']
        self.assertEqual(arr['mean'].dtype.names,
                         ('0.010000', '0.100000', '0.200000'))

        # check deserialization of source_model_lt
        r0, r1, r2 = self.calc.datastore['full_lt/source_model_lt']
        self.assertEqual(repr(r0),
                         "<Realization #0 ['source_model_1.xml', None], "
                         "path=SM1~., weight=0.5>")
        self.assertEqual(repr(r1), "<Realization #1 ['source_model_2.xml', "
                         "(3.2, 0.8)], path=SM2~a3pt2b0pt8, "
                         "weight=0.25>")
        self.assertEqual(repr(r2), "<Realization #2 ['source_model_2.xml', "
                         "(3.0, 1.0)], path=SM2~a3b1, weight=0.25>")

    def test_case_16(self):   # sampling
        with unittest.mock.patch.dict(config.memory, limit=240):
            self.assert_curves_ok(
                ['hazard_curve-mean.csv',
                 'quantile_curve-0.1.csv',
                 'quantile_curve-0.9.csv'],
                case_16.__file__)

        # test that the single realization export fails because
        # individual_rlzs was false
        with self.assertRaises(KeyError) as ctx:
            export(('hcurves/rlz-3', 'csv'), self.calc.datastore)
        self.assertIn('hcurves-rlzs', str(ctx.exception))

    def test_case_17(self):  # oversampling
        # this is a test with 4 sources A and B with the same ID
        # sources A's are actually different, while the B's are identical
        self.assert_curves_ok(
            ['hazard_curve-smltp_b1-gsimltp_b1-ltr_0.csv',
             'hazard_curve-smltp_b2-gsimltp_b1-ltr_1.csv',
             'hazard_curve-smltp_b2-gsimltp_b1-ltr_2.csv',
             'hazard_curve-smltp_b2-gsimltp_b1-ltr_3.csv',
             'hazard_curve-smltp_b2-gsimltp_b1-ltr_4.csv'],
            case_17.__file__)
        ids = decode(self.calc.datastore['source_info']['source_id'])
        numpy.testing.assert_equal(ids, ['A;0', 'A;1', 'B'])

    def test_case_20(self):
        # Source geometry enumeration, apply_to_sources
        self.assert_curves_ok([
            'hazard_curve-mean-PGA.csv',
            'hazard_curve-smltp_sm1_sg1_cog1_char_complex-gsimltp_Sad1997.csv',
            'hazard_curve-smltp_sm1_sg1_cog1_char_plane-gsimltp_Sad1997.csv',
            'hazard_curve-smltp_sm1_sg1_cog1_char_simple-gsimltp_Sad1997.csv',
            'hazard_curve-smltp_sm1_sg1_cog2_char_complex-gsimltp_Sad1997.csv',
            'hazard_curve-smltp_sm1_sg1_cog2_char_plane-gsimltp_Sad1997.csv',
            'hazard_curve-smltp_sm1_sg1_cog2_char_simple-gsimltp_Sad1997.csv',
            'hazard_curve-smltp_sm1_sg2_cog1_char_complex-gsimltp_Sad1997.csv',
            'hazard_curve-smltp_sm1_sg2_cog1_char_plane-gsimltp_Sad1997.csv',
            'hazard_curve-smltp_sm1_sg2_cog1_char_simple-gsimltp_Sad1997.csv',
            'hazard_curve-smltp_sm1_sg2_cog2_char_complex-gsimltp_Sad1997.csv',
            'hazard_curve-smltp_sm1_sg2_cog2_char_plane-gsimltp_Sad1997.csv',
            'hazard_curve-smltp_sm1_sg2_cog2_char_simple-gsimltp_Sad1997.csv'],
            case_20.__file__, delta=1E-7)
        # there are 3 sources x 12 sm_rlzs
        sgs = self.calc.csm.src_groups  # 7 source groups with 1 source each
        self.assertEqual(len(sgs), 7)
        dupl = sum(len(sg.sources[0].trt_smrs) - 1 for sg in sgs)
        self.assertEqual(dupl, 29)  # there are 29 duplicated sources

        # another way to look at the duplicated sources; protects against
        # future refactorings breaking the pandas readability of source_info
        df = self.calc.datastore.read_df('source_info', 'source_id')
        numpy.testing.assert_equal(
            decode(list(df.index)),
            ['CHAR1;0', 'CHAR1;1', 'CHAR1;2', 'COMFLT1;0', 'COMFLT1;1',
             'SFLT1;0', 'SFLT1;1'])

        # check pandas readability of hcurves-rlzs and hcurves-stats
        df = self.calc.datastore.read_df('hcurves-rlzs', 'lvl')
        self.assertEqual(list(df.columns),
                         ['site_id', 'rlz_id', 'imt', 'value'])
        df = self.calc.datastore.read_df('hcurves-stats', 'lvl')
        self.assertEqual(list(df.columns),
                         ['site_id', 'stat', 'imt', 'value'])

    def test_case_20_bis(self):
        # disagg_by_src
        self.run_calc(case_20.__file__, 'job_bis.ini')
        dbs = self.calc.datastore['disagg_by_src']
        attrs = json.loads(dbs.attrs['json'])
        self.assertEqual(attrs, {
            'shape_descr': ['site_id', 'imt', 'lvl', 'src_id'],
            'site_id': 1,
            'imt': ['PGA', 'SA(1.0)'],
            'lvl': 4,
            'src_id': ['CHAR1', 'COMFLT1', 'SFLT1']})

        # testing extract_disagg_by_src
        aw = extract(self.calc.datastore, 'disagg_by_src?imt=PGA&poe=1E-3')
        self.assertEqual(aw.site_id, 0)
        self.assertEqual(aw.imt, 'PGA')
        self.assertEqual(aw.poe, .001)
        # the numbers are quite different on macOS, 6.461143e-05 :-(
        aac(aw.array['poe'], [6.467104e-05, 0, 0], atol=1E-7)

        # testing view_relevant_sources
        arr = view('relevant_sources:SA(1.0)', self.calc.datastore)
        self.assertEqual(decode(arr['src_id']), ['SFLT1'])

    def test_case_21(self):
        # Simple fault dip and MFD enumeration
        self.assert_curves_ok([
            'hazard_curve-smltp_b1_mfd1_high_dip_dip30-gsimltp_Sad1997.csv',
            'hazard_curve-smltp_b1_mfd1_high_dip_dip45-gsimltp_Sad1997.csv',
            'hazard_curve-smltp_b1_mfd1_high_dip_dip60-gsimltp_Sad1997.csv',
            'hazard_curve-smltp_b1_mfd1_low_dip_dip30-gsimltp_Sad1997.csv',
            'hazard_curve-smltp_b1_mfd1_low_dip_dip45-gsimltp_Sad1997.csv',
            'hazard_curve-smltp_b1_mfd1_low_dip_dip60-gsimltp_Sad1997.csv',
            'hazard_curve-smltp_b1_mfd1_mid_dip_dip30-gsimltp_Sad1997.csv',
            'hazard_curve-smltp_b1_mfd1_mid_dip_dip45-gsimltp_Sad1997.csv',
            'hazard_curve-smltp_b1_mfd1_mid_dip_dip60-gsimltp_Sad1997.csv',
            'hazard_curve-smltp_b1_mfd2_high_dip_dip30-gsimltp_Sad1997.csv',
            'hazard_curve-smltp_b1_mfd2_high_dip_dip45-gsimltp_Sad1997.csv',
            'hazard_curve-smltp_b1_mfd2_high_dip_dip60-gsimltp_Sad1997.csv',
            'hazard_curve-smltp_b1_mfd2_low_dip_dip30-gsimltp_Sad1997.csv',
            'hazard_curve-smltp_b1_mfd2_low_dip_dip45-gsimltp_Sad1997.csv',
            'hazard_curve-smltp_b1_mfd2_low_dip_dip60-gsimltp_Sad1997.csv',
            'hazard_curve-smltp_b1_mfd2_mid_dip_dip30-gsimltp_Sad1997.csv',
            'hazard_curve-smltp_b1_mfd2_mid_dip_dip45-gsimltp_Sad1997.csv',
            'hazard_curve-smltp_b1_mfd2_mid_dip_dip60-gsimltp_Sad1997.csv',
            'hazard_curve-smltp_b1_mfd3_high_dip_dip30-gsimltp_Sad1997.csv',
            'hazard_curve-smltp_b1_mfd3_high_dip_dip45-gsimltp_Sad1997.csv',
            'hazard_curve-smltp_b1_mfd3_high_dip_dip60-gsimltp_Sad1997.csv',
            'hazard_curve-smltp_b1_mfd3_low_dip_dip30-gsimltp_Sad1997.csv',
            'hazard_curve-smltp_b1_mfd3_low_dip_dip45-gsimltp_Sad1997.csv',
            'hazard_curve-smltp_b1_mfd3_low_dip_dip60-gsimltp_Sad1997.csv',
            'hazard_curve-smltp_b1_mfd3_mid_dip_dip30-gsimltp_Sad1997.csv',
            'hazard_curve-smltp_b1_mfd3_mid_dip_dip45-gsimltp_Sad1997.csv',
            'hazard_curve-smltp_b1_mfd3_mid_dip_dip60-gsimltp_Sad1997.csv'],
            case_21.__file__, delta=1E-7)

    def test_case_28(self):  # North Africa
        # MultiPointSource with modify MFD logic tree
        out = self.run_calc(case_28.__file__, 'job.ini', exports='csv')
        for f in out['uhs', 'csv']:
            self.assertEqualFiles('expected/' + strip_calc_id(f), f)

        # checking that source_info is stored correctly
        info = self.calc.datastore['source_info'][:]
        ae(info['source_id'], [b'21;0', b'21;1', b'22'])
        ae(info['grp_id'], [0, 1, 2])
        ae(info['weight'] > 0, [True, True, True])
        ae(info['trti'], [0, 0, 1])

    def test_case_31(self):
        # source specific logic tree
        self.assert_curves_ok(['hazard_curve-mean-PGA.csv',
                               'hazard_curve-std-PGA.csv'], case_31.__file__,
                              delta=1E-5)

    def test_case_36(self):
        # test with advanced applyToSources and disordered gsim_logic_tree
        self.run_calc(case_36.__file__, 'job.ini')
        hc_id = str(self.calc.datastore.calc_id)
        self.run_calc(case_36.__file__, 'job.ini', hazard_calculation_id=hc_id,
                      calculation_mode='classical')
        self.assertEqual(self.calc.R, 9)  # there are 9 realizations
        dstore = self.calc.datastore

        # test `oq show rlz:`
        tbl = general.gettemp(text_table(view('rlz:8', dstore)))
        self.assertEqualFiles('expected/show-rlz8.org', tbl)

        # test `oq show branchsets`
        tbl = general.gettemp(view('branchsets', dstore))
        self.assertEqualFiles('expected/branchsets.org', tbl)

    def test_case_45(self):
        # this is a test for MMI with disagg_by_src and sampling
        self.assert_curves_ok(["hazard_curve-mean-MMI.csv"], case_45.__file__)

    def test_case_46(self):
        # SMLT with applyToBranches
        self.assert_curves_ok(["hazard_curve-mean.csv"], case_46.__file__,
                              delta=1E-6)

    def test_case_56(self):
        # test with a discardable source model (#2)
        self.run_calc(case_56.__file__, 'job.ini', concurrent_tasks='0')
        [fname] = export(('uhs/mean', 'csv'), self.calc.datastore)
        self.assertEqualFiles('expected/uhs.csv', fname)

    def test_case_58(self):
        # Logic tree with SimpleFault uncertainty on geometry and MFD (from
        # slip)

        # First calculation
        self.run_calc(case_58.__file__, 'job.ini')
        f01, f02 = export(('hcurves/rlz-000', 'csv'), self.calc.datastore)
        f03, f04 = export(('hcurves/rlz-003', 'csv'), self.calc.datastore)

        # Second calculation. Same LT structure for case 1 but with only one
        # branch for each branch set
        self.run_calc(case_58.__file__, 'job_case01.ini')
        f11, f12 = export(('hcurves/', 'csv'), self.calc.datastore)

        # Third calculation. In this case we use a source model containing one
        # source with the geometry of branch b22 and slip rate of branch b32
        self.run_calc(case_58.__file__, 'job_case02.ini')
        f21, f22 = export(('hcurves/', 'csv'), self.calc.datastore)

        # First test
        self.assertEqualFiles(f01, f11)

        # Second test
        self.assertEqualFiles(f03, f21)

    def test_case_59(self):
        # test NRCan15SiteTerm
        self.run_calc(case_59.__file__, 'job.ini')
        [f] = export(('hcurves/mean', 'csv'), self.calc.datastore)
        self.assertEqualFiles('expected/hcurve-mean.csv', f)

    def test_case_67(self):
        # source specific logic tree with the following structure:
        # <CompositeSourceModel
        # grp_id=0 ['10;0']
        # grp_id=1 ['16']
        # grp_id=2 ['11;0']
        # grp_id=3 ['11;1']
        # grp_id=4 ['11;2']
        # grp_id=5 ['10;1']
        # grp_id=6 ['ACC;0']
        # grp_id=7 ['ALS;0']
        # grp_id=8 ['BMS;0']
        # grp_id=9 ['BMS;1']
        # grp_id=10 ['BMS;2']
        # grp_id=11 ['BMS;3']
        # grp_id=12 ['ALS;1']
        # grp_id=13 ['ALS;2']
        # grp_id=14 ['ACC;1']>
        # there are 2x2x3x2x3x4=288 realizations and 2+2+3+2+3+4=16 groups
        # 1 group has no sources so the engine sees 15 groups
        self.run_calc(case_67.__file__, 'job.ini')
        [f1] = export(('hcurves/mean', 'csv'), self.calc.datastore)
        self.assertEqualFiles('expected/hcurve-mean.csv', f1)

    def test_case_68(self):
        # extendModel feature
        self.run_calc(case_68.__file__, 'job.ini')
        [f1] = export(('hcurves/mean', 'csv'), self.calc.datastore)
        self.assertEqualFiles('expected/hcurve-mean.csv', f1)

    def test_case_68_bis(self):
        # extendModel with sampling and reduction to single source
        self.run_calc(case_68.__file__, 'job1.ini')

        # check the reduction from 1o to 2 realizations
        rlzs = extract(self.calc.datastore, 'realizations').array
        ae(rlzs['branch_path'], [b'AA~A', b'B.~A'])
        aac(rlzs['weight'], [.7, .3])

        # check the hazard curves
        fnames = export(('hcurves', 'csv'), self.calc.datastore)
        for f in fnames:
            self.assertEqualFiles('expected/' + strip_calc_id(f), f)

    def test_case_71(self):
        # test with oversampling
        # there are 6 potential paths 1A 1B 1C 2A 2B 2C
        # 10 rlzs are being sampled: 1C 1A 1B 1A 1C 1A 2B 2A 2B 2A
        # rlzs_by_g is 135 2 04, 79 68 i.e. 1A*3 1B*1 1C*1, 2A*2 2B*2
        self.run_calc(case_71.__file__, 'job.ini', concurrent_tasks='0')
        self.assertEqual(len(self.calc.realizations), 10)
        [fname] = export(('hcurves/mean', 'csv'), self.calc.datastore)
        self.assertEqualFiles('expected/hcurves.csv', fname)

        cmakers = contexts.read_cmakers(self.calc.datastore)
        ae(list(cmakers[0].gsims.values()), [[1, 3, 5], [2], [0, 4]])
        ae(list(cmakers[1].gsims.values()), [[7, 9], [6, 8]])
        # there are two slices 0:3 and 3:5 with length 3 and 2 respectively

        # testing unique_paths mode
        self.run_calc(case_71.__file__, 'job.ini', concurrent_tasks='0',
                      oversampling='reduce-rlzs')
        self.assertEqual(len(self.calc.realizations), 5)
        [fname] = export(('hcurves/mean', 'csv'), self.calc.datastore)
        self.assertEqualFiles('expected/hcurves.csv', fname)

    def test_case_73(self):
        # test LT
        self.run_calc(case_73.__file__, 'job.ini')
        [f1] = export(('hcurves/mean', 'csv'), self.calc.datastore)
        self.assertEqualFiles('expected/hcurve-mean.csv', f1)

    def test_case_79(self):
        # disagg_by_src with semicolon sources
        self.run_calc(case_79.__file__, 'job.ini')

    def test_case_83(self):
        # two mps, only one should be collapsed and use reqv
        self.run_calc(case_83.__file__, 'job_extendModel.ini')
        [fname_em] = export(('hcurves/mean', 'csv'), self.calc.datastore)
        self.run_calc(case_83.__file__, 'job_expanded_LT.ini')
        [fname_ex] = export(('hcurves/mean', 'csv'), self.calc.datastore)
        self.assertEqualFiles(fname_em, fname_ex)
