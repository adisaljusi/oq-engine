# -*- coding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright (C) 2012-2021 GEM Foundation
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

from openquake.hazardlib.gsim.yu_2013 import (YuEtAl2013Mw, YuEtAl2013MwTibet,
                                              YuEtAl2013MwEastern,
                                              YuEtAl2013MwStable)


from openquake.hazardlib.tests.gsim.utils import BaseGSIMTestCase


class YuEtAl2013MwActiveTestCase(BaseGSIMTestCase):
    GSIM_CLASS = YuEtAl2013Mw

    def test_all(self):
        self.check_all('YU2013Mw/yu_2013_mean_active.csv',
                       'YU2013Mw/yu_2013_stddev_active.csv',
                       mean_discrep_percentage=0.4,
                       std_discrep_percentage=0.1)


class YuEtAl2013MwTibetTestCase(BaseGSIMTestCase):
    GSIM_CLASS = YuEtAl2013MwTibet

    def test_all(self):
        self.check_all('YU2013Mw/yu_2013_mean_tibetan.csv',
                       'YU2013Mw/yu_2013_stddev_tibetan.csv',
                       mean_discrep_percentage=0.4,
                       std_discrep_percentage=0.1)


class YuEtAl2013MwEasternTestCase(BaseGSIMTestCase):
    GSIM_CLASS = YuEtAl2013MwEastern

    def test_all(self):
        self.check_all('YU2013Mw/yu_2013_mean_eastern.csv',
                       'YU2013Mw/yu_2013_stddev_eastern.csv',
                       mean_discrep_percentage=0.4,
                       std_discrep_percentage=0.1)


class YuEtAl2013MwStableTestCase(BaseGSIMTestCase):
    GSIM_CLASS = YuEtAl2013MwStable

    def test_all(self):
        self.check_all('YU2013Mw/yu_2013_mean_stable.csv',
                       'YU2013Mw/yu_2013_stddev_stable.csv',
                       mean_discrep_percentage=0.4,
                       std_discrep_percentage=0.1)
