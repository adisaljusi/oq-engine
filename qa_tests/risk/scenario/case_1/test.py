# Copyright (c) 2010-2013, GEM Foundation.
#
# OpenQuake is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OpenQuake is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with OpenQuake.  If not, see <http://www.gnu.org/licenses/>.

import os
import csv

import numpy
from nose.plugins.attrib import attr

from qa_tests import risk
from tests.utils import helpers
from openquake.engine.db import models


class ScenarioRiskCase1TestCase(risk.BaseRiskQATestCase):
    cfg = os.path.join(os.path.dirname(__file__), 'job.ini')

    @attr('qa', 'risk', 'scenario')
    def test(self):
        self._run_test()

    def hazard_id(self):
        job = helpers.get_hazard_job(
            helpers.demo_file("scenario_hazard/job.ini"))
        hc = job.hazard_calculation
        job.hazard_calculation = models.HazardCalculation.objects.create(
            owner=hc.owner, truncation_level=hc.truncation_level,
            maximum_distance=hc.maximum_distance,
            intensity_measure_types=["PGA"],
            calculation_mode="scenario")
        job.status = "complete"
        job.save()

        output = models.Output.objects.create_output(
            job, "Test Hazard output", "gmf_scenario")

        fname = os.path.join(os.path.dirname(__file__), 'gmf_scenario.csv')
        with open(fname, 'rb') as csvfile:
            gmfreader = csv.reader(csvfile, delimiter=',')
            locations = gmfreader.next()

            arr = numpy.array([[float(x) for x in row] for row in gmfreader])
            for i, gmvs in enumerate(arr):
                models.GmfScenario.objects.create(
                    output=output,
                    imt="PGA",
                    gmvs=gmvs,
                    location="POINT(%s)" % locations[i])
        return output.id

    def actual_data(self, job):
        maps = models.LossMapData.objects.filter(
            loss_map__output__oq_job=job,
            loss_map__insured=False).order_by('asset_ref', 'value')
        agg = models.AggregateLoss.objects.get(output__oq_job=job,
                                               insured=False)
        insured_maps = models.LossMapData.objects.filter(
            loss_map__output__oq_job=job,
            loss_map__insured=True).order_by('asset_ref', 'value')
        insured_agg = models.AggregateLoss.objects.get(
            output__oq_job=job,
            insured=True)

        return [[[m.value, m.std_dev] for m in maps],
                [agg.mean, agg.std_dev],
                [[m.value, m.std_dev] for m in insured_maps],
                [insured_agg.mean, insured_agg.std_dev]]

    def expected_data(self):
        return [[[440.14707, 182.6159],
                 [432.2254, 186.8644],
                 [180.7175, 92.2122]],
                [1053.09, 246.62],
                [[327.492087529, 288.47906994],
                 [314.859579324, 293.976254984],
                 [156.750910806, 100.422061776]],
                [799.102578, 382.148808]]
