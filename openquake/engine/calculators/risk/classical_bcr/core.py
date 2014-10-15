# Copyright (c) 2010-2014, GEM Foundation.
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

"""
Core functionality for the classical PSHA risk calculator.
"""

from openquake.risklib import workflows

from openquake.engine.calculators.risk import (
    hazard_getters, writers, validation)
from openquake.engine.calculators.risk.classical_risk import core as classical


def classical_bcr(workflow, risk_input, outputdict, params, monitor):
    """
    Celery task for the BCR risk calculator based on the classical
    calculator.

    Instantiates risklib calculators, computes BCR and stores the
    results to db in a single transaction.

    :param int job_id:
      ID of the currently running job
    :param workflow:
      A :class:`openquake.risklib.workflows.RiskModel` instance
    :param risk_input:
      A RiskInput instance
    :param outputdict:
      An instance of :class:`..writers.OutputDict` containing
      output container instances (in this case only `BCRDistribution`)
    :param params:
      An instance of :class:`..base.CalcParams` used to compute
      derived outputs
    :param monitor:
      An instance of :class:
      `openquake.engine.db.models.EnginePerformanceMonitor`
    """
    for loss_type in workflow.loss_types:
        with monitor.copy('computing risk'):
            outputs = workflow.compute_all_outputs(risk_input, loss_type, monitor)
        outputdict = outputdict.with_args(loss_type=loss_type)
        with monitor.copy('saving risk'):
            for out in outputs:
                outputdict.write(
                    workflow.assets,
                    out.output,
                    output_type="bcr_distribution",
                    hazard_output_id=out.hid)


class ClassicalBCRRiskCalculator(classical.ClassicalRiskCalculator):
    """
    Classical BCR risk calculator. Computes BCR distributions for a
    given set of assets.

    :attr dict vulnerability_functions_retrofitted:
        A dictionary mapping each taxonomy to a vulnerability functions for the
        retrofitted losses computation
    """
    core = staticmethod(classical_bcr)

    validators = classical.ClassicalRiskCalculator.validators + [
        validation.ExposureHasRetrofittedCosts]

    output_builders = [writers.BCRMapBuilder]

    risk_input_class = hazard_getters.HazardCurveInput

    bcr = True

    def get_workflow(self, vf_orig, vf_retro):
        return workflows.ClassicalBCR(
            vf_orig, vf_retro,
            self.rc.lrem_steps_per_interval,
            self.rc.interest_rate,
            self.rc.asset_life_expectancy)
