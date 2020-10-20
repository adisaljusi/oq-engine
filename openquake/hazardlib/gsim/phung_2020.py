# -*- coding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright (C) 2015-2018 GEM Foundation
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

"""
Module exports :class:`PhungEtAl2020SInter`
               :class:`PhungEtAl2020SSlab`
               :class:`PhungEtAl2020Asc`
"""
import math

import numpy as np
from scipy.special import erf

from openquake.hazardlib import const
from openquake.hazardlib.gsim.base import GMPE, CoeffsTable, gsim_aliases
from openquake.hazardlib.imt import PGA, SA, PGV


class PhungEtAl2020Asc(GMPE):
    """
    Implements Phung et al. (2020) for crustal.
    """

    DEFINED_FOR_TECTONIC_REGION_TYPE = const.TRT.ACTIVE_SHALLOW_CRUST

    DEFINED_FOR_INTENSITY_MEASURE_TYPES = set([PGA, SA])

    DEFINED_FOR_INTENSITY_MEASURE_COMPONENT = const.IMC.AVERAGE_HORIZONTAL

    DEFINED_FOR_STANDARD_DEVIATION_TYPES = set([
        const.StdDev.TOTAL,
        const.StdDev.INTER_EVENT,
        const.StdDev.INTRA_EVENT
    ])

    REQUIRES_SITES_PARAMETERS = {'vs30', 'z1pt0'}

    REQUIRES_RUPTURE_PARAMETERS = {'dip', 'mag', 'rake', 'ztor'}

    # rx for hanging wall
    REQUIRES_DISTANCES = {'rjb', 'rrup', 'rx'}

    def __init__(region='glb', aftershocks=False, d_dpp=0, **kwargs):
        super().__init__(region=region, aftershocks=aftershocks, d_dpp=d_dpp, \
                         **kwargs)

        # region options:
        # 'glb', 'tw', 'ca', 'jp' (global, Taiwan, California, Japan)
        self.region = region
        # only for Taiwan region
        self.aftershocks = aftershocks and region == 'tw'
        # direct point parameter for directivity effect
        self.d_ddp = d_ddp

    def get_mean_and_stddevs(self, sites, rup, dists, imt, stddev_types):
        """
        See :meth:`superclass method
        <.base.GroundShakingIntensityModel.get_mean_and_stddevs>`
        for spec of input and result values.
        """
        # extract dictionaries of coefficients specific to IM type
        C = self.COEFFS[imt]

        lnmed, ztor = self._fsof_ztor(C, rup.mag, rup.rake, rup.ztor)
        # main shock [1]
        lnmed += C['c1']
        # dip term [5]
        lnmed += (C['c11'] + C['c11_b'] / math.cosh(2 * max(mag - 4.5, 0))) \
            * (math.cos(math.radians(rup.dip)) ** 2)
        # hanging wall term [12]
        lnmed += (dists.rx >= 0) * C['c9'] * math.cos(math.radians(rup.dip)) \
            * (C['c9_a'] + (1 - C['c9_a']) * np.tanh(dists.rx / C['c9_b'])) \
            * (1 - np.sqrt(dists.rjb ** 2 + ztor ** 2) / (dists.rrup + 1))
        # directivity [11]
        lnmed += C['c8'] * max(1 - max(dists.rrup - 40, 0) / 30, 0) \
            * min(max(mag - 5.5, 0) / 0.8, 1) \
            * exp(self.CONSTANTS['c8_a'] * (mag - C['c8_b']) ** 2) * self.d_ddp
        # fmag [6, 7]
        lnmed += self.CONSTANTS['c2'] * (mag - 6)
        lnmed += (self.CONSTANTS['c2'] - C['c3']) / C['c_n'] \
            * math.log(1 + math.exp(C['c_n'] * (C['c_m'] - mag)))
        lnmed += self._distance_attenuation(C, rup.mag, ztor)

        sa1130 = exp(lnmed)
        # site response [14, 15]
        lnmed += C['phi1' + self.region] * min(np.log(sites.vs30 / 1130), 0)
        lnmed += C['phi2'] * (exp(C['phi3'] * (min(sites.vs30, 1130) - 360)) \
            - exp(C['phi3'] * (1130 - 360))) * log((sa1130 + C['phi4']) / C['phi4'])
        # basin term [16]
        lnmed += self._basin_term(C, sites.vs30, sites.z1pt0)

        stddevs = self.get_stddevs(C, stddev_types)

        return lnmed, stddevs

    def get_stddevs(self, C, stddev_types):
        """
        Return standard deviations.
        """
        # variance Model-2 for Taiwan
        # why is tau mixed with ss/s2s?
        sig_ss = math.sqrt(C['tau'] ** 2 + C['phiss'] ** 2)
        sig_t = math.sqrt(C['tau'] ** 2 + C['phiss'] ** 2 + C['phis2s'] ** 2)

        for stddev in stddev_types:
            assert stddev in self.DEFINED_FOR_STANDARD_DEVIATION_TYPES
            if stddev == const.StdDev.TOTAL:
                stddevs.append(np.sqrt(C["Tau"] ** 2 + phi_tot ** 2))
            elif stddev == const.StdDev.INTER_EVENT:
                stddevs.append(C["tau"])
            elif stddev == const.StdDev.INTRA_EVENT:
                stddevs.append(phi_tot)

        return stddevs

    def _basin_term(self, C, vs30, z1pt0):
        """
        Basin term [16].
        """
        if self.region == 'glb':
            return 0

        if self.region == 'tw':
            ez_1 = np.exp(-3.73 / 2 * np.log((vs30 ** 2 + 290.53 ** 2)
                                             / (1750 ** 2 + 290.53 ** 2)))
            phi6 = 300
        elif self.region in ['ca', 'jp']:
            ez_1 = np.exp(-5.23 / 2 * np.log((vs30 ** 2 + 412.39 ** 2)
                                             / (1360 ** 2 + 412.39 ** 2)))
            if region == 'ca':
                phi6 = 300
            else:
                phi6 = 800

        d_z1 = z1pt0 - ez_1
        return np.where(np.isnan(sites.z1pt0), 0,
                        C['phi5' + self.region] * (1 - np.exp(-d_z1 / phi6)))

    def _distance_attenuation(self, C, mag, ztor):
        """
        Distance scaling and attenuation term [8, 9, 10].
        """
        del_c5 = C['dp'] * max(ztor / 50 - 20 / 50, 0) \
            * (ztor > 20) * (mag < 7.0)
        cns = (C['c5'] + del_c5) * math.cosh(C['c6'] * max(mag - C['c_hm'], 0))
        s = self.CONSTANTS

        f8 = s['c4'] * np.log(dists.rrup + CNS)
        f9 = (s['c4_a'] - s['c4']) * np.log(np.sqrt(dists.rrup ** 2 \
                                                    + C['c_rb'] ** 2))
        f10 = (C['c_g1' + self.region] + self.aftershocks * C['dc_g1as'] \
            + C['c_g2'] / (math.cosh(max(mag - C['c_g3'], 0)))) * dists.rrup

        return f8 + f9 + f10

    def _fsof_ztor(C, mag, rake, ztor):
            """
            Factors requiring type of fault.
            """
            f234 = 0
            if 30 <= rake <= 150:
                e_ztor = (max(3.5384 - 2.60 * max(mag - 5.8530, 0), 0)) ** 2
                # reverse fault [2]
                f234 += C['c1_a'] \
                    + C['c1_c'] / math.cosh(2 * max(mag - 4.5, 0))
            else:
                e_ztor = max(2.7482 - 1.7639 * max(mag - 5.5210, 0), 0) ** 2
                if -120 <= rake <= -60:
                    # normal fault [3]
                    f234 += C['c1_b'] \
                        + C['c1_d'] / math.cosh(2 * max(mag - 4.5, 0))

            ztor = np.where(np.isnan(ztor), e_ztor, ztor
            delta_ztor = ztor - e_ztor
            # [4]
            f234 += (C['c7'] + C['c7_b'] / math.cosh(2 * max(mag - 4.5, 0))) \
                * delta_ztor

            return f234, ztor

    COEFFS = CoeffsTable(sa_damping=5, table="""\
     imt    c1     c1_a         c1_b        c1_c         c1_d        c3     c5     c6      c7           c7_b        c8     c8_b   c9     c9_a   c9_b    c11         c11_b        c12         c12_b        c_n         c_m      c_g2        c_g3        c_hm    dp           phi2    phi3     phi4      c_g1tw     phi1tw       dc_g1as      c_g1ca       phi1ca      c_g1jp        phi1jp       c_g1glb      phi1glb     phi5tw  phi5ca      phi5jp      tau         phiss  phis2s
     PGA   -1.4526 0.137929376  0           0.04272907  -0.165254064 1.4379 6.4551 0.4908  0.00803536   0.021034339 0.0000 0.4833 0.9228 0.1202 6.8607 -0.108037007 0.195951708 -1.282688908 0.029231406 12.14866822  5.50455 -0.007127092 4.225634814 3.0956 -6.785205271 -0.1417 -0.007010 0.102151 -0.0087980 -0.510745033 -0.00148591  -0.006937324 -0.484221897 -0.009554995 -0.535583503 -0.008207338 -0.505350491 0.07436 0.032134169 0.092181936 0.372991982 0.4397 0.3149
     0.01  -1.4468 0.131008944  0           0.05491546  -0.164615502 1.4379 6.4551 0.4908  0.00803536   0.021034339 0.0000 0.4833 0.9228 0.1202 6.8607 -0.108037007 0.195951708 -1.282688908 0.029231406 12.14866822  5.51303 -0.007127092 4.225634814 3.0956 -6.750647967 -0.1417 -0.007010 0.102151 -0.0087980 -0.510415026 -0.001553994 -0.006982409 -0.481325676 -0.009621694 -0.527374167 -0.008266685 -0.504993164 0.07436 0.031948851 0.091289209 0.372455184 0.4388 0.3149
     0.02  -1.4066 0.124713602  0           0.06599634  -0.166706035 1.4030 6.4551 0.4925  0.007592927  0.021638743 0.0000 1.2144 0.9296 0.1217 6.8697 -0.102071888 0.181778172 -1.219189069 0.029463211 12.24803407  5.51745 -0.007248737 4.230341898 3.0963 -6.716179208 -0.1364 -0.007279 0.108360 -0.0090670 -0.502941955 -0.001332937 -0.007105962 -0.473436602 -0.009678565 -0.509697529 -0.008372404 -0.497396753 0.07359 0.032083196 0.087461387 0.37404339  0.4391 0.3148
     0.03  -1.3175 0.119040284  0           0.075907583 -0.19413385  1.3628 6.4551 0.4992  0.007250488  0.022052403 0.0000 1.6421 0.9396 0.1194 6.9113 -0.104638092 0.163170085 -1.129842391 0.029897695 12.53378414  5.51798 -0.007327856 4.236182109 3.0974 -6.681798923 -0.1403 -0.007354 0.119888 -0.0094510 -0.491366306 -0.001500854 -0.007654162 -0.460829876 -0.010021137 -0.481412435 -0.008893062 -0.484084547 0.07713 0.031462124 0.085075638 0.386799496 0.4451 0.3223
     0.04  -1.1970 0.113983621  0           0.08465752  -0.2133523   1.3168 6.4551 0.5037  0.007006048  0.022283866 0.0000 1.9456 0.9661 0.1166 7.0271 -0.105159212 0.142063237 -1.009367871 0.030887621 12.99189704  5.51462 -0.007361759 4.250188668 3.0988 -6.647507037 -0.1591 -0.006977 0.133641 -0.0098320 -0.474484696 -0.001727377 -0.008235534 -0.442342385 -0.010348898 -0.433457113 -0.009471857 -0.464454841 0.08249 0.034324999 0.078902251 0.400724323 0.4516 0.3347
     0.05  -1.0642 0.109535952  0           0.092384148 -0.246430796 1.2552 6.4551 0.5048  0.006860143  0.022340988 0.0000 2.1810 0.9794 0.1176 7.0959 -0.09694663  0.098053885 -0.864733627 0.03256833  13.65075358  5.50692 -0.007360913 4.303122568 3.1011 -6.613303475 -0.1862 -0.006467 0.148927 -0.0101940 -0.459984157 -0.002042414 -0.008985334 -0.404306111 -0.010606375 -0.35987791  -0.009965209 -0.441619243 0.09010 0.031188831 0.068543862 0.415407087 0.4555 0.3514
     0.075 -0.7737 0.101016047  0           0.109529939 -0.240863766 1.1873 6.4551 0.5048  0.007007726  0.021712418 0.0000 2.6087 1.0260 0.1171 7.3298 -0.079174009 0.046296818 -0.543806592 0.034602039 15.71447541  5.43078 -0.007051574 4.446126947 3.1094 -6.52818049  -0.2538 -0.005734 0.190596 -0.0109620 -0.446396645 -0.002375719 -0.010178327 -0.385991895 -0.010285208 -0.227565057 -0.010848089 -0.418370706 0.10291 0.022101594 0.031193656 0.425118035 0.4558 0.3845
     0.1   -0.5958 0.096066418  0           0.11002146  -0.22991286  1.2485 6.8305 0.5048  0.007246641  0.020031223 0.0000 2.9122 1.0177 0.1146 7.2588 -0.120806584 0.173997245 -0.372706269 0.035821539 16.77262242  5.42081 -0.005719182 4.610835161 3.2381 -6.443607867 -0.2943 -0.005604 0.230662 -0.0114520 -0.476282069 -0.002929177 -0.010859197 -0.431169291 -0.010753951 -0.279289236 -0.01136162  -0.448999162 0.12596 0.030782851 0.087905262 0.416469357 0.4497 0.3935
     0.12  -0.5229 0.094563811  0           0.101539072 -0.171017133 1.3263 7.1333 0.5048  0.007455965  0.018584674 0.0000 3.1045 1.0008 0.1128 7.2372 -0.127655488 0.209294889 -0.361923917 0.028768271 16.77563032  5.46158 -0.00436511  4.723496543 3.3407 -6.376345237 -0.3077 -0.005696 0.253169 -0.0115970 -0.4931516   -0.002868694 -0.010797857 -0.449168755 -0.01131987  -0.348471281 -0.011514176 -0.469073942 0.11942 0.039955704 0.135335734 0.402380557 0.4429 0.3897
     0.15  -0.5005 0.096331606  0           0.081268087 -0.13673324  1.4098 7.3621 0.5045  0.00770271   0.016544376 0.0000 3.3399 0.9801 0.1106 7.2109 -0.123958373 0.217339629 -0.406746707 0.025510321 16.18679785  5.55373 -0.002649555 4.878140618 3.4300 -6.276109027 -0.3113 -0.005845 0.266468 -0.0115790 -0.517925624 -0.002692777 -0.010419656 -0.468824982 -0.011809781 -0.440922758 -0.011431783 -0.499329355 0.10019 0.029374116 0.134933456 0.382176649 0.4382 0.3713
     0.17  -0.5165 0.100411816  0           0.066332395 -0.085084587 1.4504 7.4365 0.5036  0.007798775  0.015412673 0.0000 3.4719 0.9652 0.1150 7.2491 -0.120234904 0.218818569 -0.430596429 0.026722101 15.84314399  5.60449 -0.001999512 4.981707053 3.4688 -6.209722535 -0.3062 -0.005959 0.265060 -0.0113030 -0.532965478 -0.002436738 -0.009960427 -0.497020598 -0.011945969 -0.509266123 -0.01109686  -0.521025765 0.08862 0.038181875 0.177785878 0.371903621 0.4385 0.3632
     0.2   -0.5558 0.113754448  0           0.047001724 -0.078934463 1.5274 7.4972 0.5016  0.007823121  0.014410752 0.0000 3.6434 0.9459 0.1208 7.2988 -0.128554524 0.262936287 -0.517179185 0.024730499 15.01467129  5.64383 -0.001254506 5.066410859 3.5146 -6.110797854 -0.2927 -0.006141 0.255253 -0.0108190 -0.547665313 -0.002502554 -0.009509403 -0.524364877 -0.012104115 -0.595400115 -0.010650653 -0.542326413 0.08048 0.048572809 0.147248099 0.357414054 0.4395 0.3503
     0.25  -0.6550 0.132878713 -0.034932397 0.018708157  0.000000286 1.6737 7.5416 0.4971  0.00807121   0.013237789 0.0000 3.8787 0.9196 0.1208 7.3691 -0.104990465 0.231024464 -0.683634944 0.01982955  12.69643148  5.66058 -0.00075041  5.21986472  3.5746 -5.947665543 -0.2662 -0.006439 0.231541 -0.0100190 -0.565549294 -0.002342412 -0.008707306 -0.573301197 -0.012011131 -0.708979498 -0.009707027 -0.570861885 0.08000 0.052015826 0.122156442 0.337728984 0.4433 0.3343
     0.3   -0.7898 0.147312358 -0.052793111 0            0           1.8298 7.5600 0.4919  0.008395901  0.011957864 0.0000 4.0711 0.8829 0.1175 6.8789 -0.125335213 0.27034386  -0.85881890  0.018366075 10.44981091  5.65301 -0.000447155 5.32821979  3.6232 -5.786703295 -0.2405 -0.006704 0.207277 -0.0092670 -0.606451856 -0.002040929 -0.007614433 -0.60870418  -0.011583213 -0.792224081 -0.008888726 -0.616028974 0.08013 0.046520626 0.063742847 0.359262599 0.4498 0.3324
     0.4   -1.0839 0.158162078 -0.096705093 0            0           2.0330 7.5735 0.4807  0.00927498   0.00946882  0.0000 4.3745 0.8302 0.1060 6.5334 -0.131458922 0.306056087 -1.167698273 0.015383491  6.802216656 5.62843 -0.000247246 5.201761713 3.6945 -5.47125339  -0.1975 -0.007125 0.165464 -0.0079030 -0.653316566 -0.001429428 -0.0063373   -0.672656694 -0.010377611 -0.867597085 -0.007382039 -0.667318538 0.07916 0.087073138 0.182053316 0.397614543 0.4590 0.3299
     0.5   -1.3279 0.163112167 -0.121161057 0            0           2.2044 7.5778 0.4707  0.010165826  0.005799966 0.0991 4.6099 0.7884 0.1061 6.5260 -0.102606613 0.272617073 -1.414494521 0.015996408  4.41069375  5.59326 -0.000416797 5.187931728 3.7401 -5.164376146 -0.1633 -0.007435 0.133828 -0.0069990 -0.674933921 -0.001044295 -0.005515638 -0.733923523 -0.009392201 -0.922617109 -0.006165716 -0.693380936 0.07543 0.090202859 0.179683104 0.426900573 0.4703 0.3319
     0.75  -1.9346 0.169389333 -0.158672494 0            0           2.4664 7.5808 0.4575  0.012793392 -0.003683309 0.1982 5.0376 0.6754 0.1000 6.5000 -0.072842909 0.265158493 -1.915634927 0.020897161  3.4064      5.56641 -0.001131462 4.877209058 3.7941 -4.4342041   -0.1028 -0.008120 0.085153 -0.0054380 -0.796961941  0           -0.003324985 -0.844223441 -0.007154876 -1.024238579 -0.004216545 -0.814440958 0.07573 0.068955592 0.355638284 0.466977537 0.4707 0.3384
     1.0   -2.3932 0.177254643 -0.184203622 0            0           2.6194 7.5814 0.4522  0.013761922 -0.008131001 0.2154 5.3411 0.6196 0.1000 6.5000 -0.072286657 0.303895403 -2.405746274 0.013663365  3.1612      5.60836 -0.001741492 4.63975087  3.8144 -3.75596604  -0.0699 -0.008444 0.058595 -0.0045400 -0.884871551  0           -0.002895489 -0.932541432 -0.005643852 -1.052091854 -0.003321554 -0.896887535 0.07941 0.0901      0.446281385 0.495441465 0.4643 0.3480
     1.5   -2.9412 0.17612706  -0.218917854 0            0           2.7708 7.5817 0.4501  0.013899933 -0.010287269 0.2154 5.7688 0.5101 0.1000 6.5000 -0.143270261 0.443286099 -3.076775856 0.012057836  2.8078      5.73551 -0.002427965 4.571203643 3.8284 -2.55026692  -0.0425 -0.007707 0.031787 -0.0036370 -0.958271065  0           -0.001749137 -0.98261014  -0.004814825 -1.088340342 -0.002382593 -0.966713194 0.12820 0.131818315 0.718324249 0.487074394 0.4568 0.3697
     2.0   -3.2794 0.161185738 -0.218956446 0            0           2.8699 7.5818 0.4500  0.012559337 -0.008563294 0.2154 6.0723 0.3917 0.1000 6.5000 -0.171095562 0.520454201 -3.344039931 0.009195969  2.4631      5.85199 -0.002705545 4.425116502 3.8330 -1.536847647 -0.0302 -0.004792 0.019716 -0.0029726 -0.968084348  0           -0.001160868 -0.95905628  -0.005047271 -1.086834766 -0.002166838 -0.973218415 0.16687 0.171872332 0.767882913 0.477953808 0.4521 0.3826
     3.0   -3.5891 0.112720638 -0.218956446 0            0           2.9293 7.5818 0.4500  0.009183764 -0.003058727 0.2154 6.5000 0.1244 0.1000 6.5000 -0.269171794 0.817526599 -3.621193267 0.006748877  2.2111      6.08195 -0.004107346 3.6219035   3.8361 -0.052837841 -0.0129 -0.001828 0.009643 -0.0024872 -0.96759396   0           -0.001243607 -0.913057084 -0.004730659 -1.017732708 -0.002207237 -0.965187761 0.20292 0.152581614 0.92637631  0.436531699 0.4524 0.3974
     4.0   -3.8483 0.053953075 -0.218956446 0            0           3.0012 7.5818 0.4500  0.004796976  0.003919649 0.2154 6.8035 0.0086 0.1000 6.5000 -0.321537372 1.015932218 -3.870076534 0.004630924  1.9668      6.25683 -0.005776395 3.48626393  3.8369  0           -0.0016 -0.001523 0.005379 -0.0021234 -0.964753341  0           -0.001243607 -0.933614579 -0.003087049 -0.910235842 -0.001854414 -0.956076432 0.17899 0.187006538 0.881214487 0.449129802 0.4461 0.3983
     5.0   -3.9458 0.053953075 -0.218956446 0            0           3.0012 7.5818 0.4500  0.001067909  0.013063958 0.2154 7.0389 0.0000 0.1000 6.5000 -0.344321787 0.892205391 -3.941815776 0            1.6671      6.39882 -0.007747849 3.277906342 3.8376  0            0.0000 -0.001440 0.003223 -0.0017638 -0.923270348  0           -0.001243607 -0.852999852 -0.001983904 -0.801       -0.001525789 -0.90692656  0.17368 0.206446726 0.891977077 0.46456534  0.4420 0.3985
     7.5   -4.2514 0.053953075 -0.218956446 0            0           3.0012 7.5818 0.4500 -0.004234005  0.027920315 0.2154 7.4666 0.0000 0.1000 6.5000 -0.379466889 0.86436398  -4.193292591 0            1.5737      6.66908 -0.009141588 3.074948086 3.8380  0            0.0000 -0.001369 0.001134 -0.0010788 -0.85471647   0           -0.001243607 -0.731675782  0.000347579 -0.547       -0.001034361 -0.806827389 0.15176 0.264763991 0.83242751  0.505675779 0.4177 0.3878
    10.0   -4.5075 0.053953075 -0.218956446 0            0           3.0012 7.5818 0.4500 -0.006203311  0.04195315  0.2154 7.7700 0.0000 0.1000 6.5000 -0.478010668 1.443597529 -4.33514388  0            1.5265      6.84353 -0.012633296 3.074948086 3.8380  0            0.0000 -0.001361 0.000515 -0.0007423 -0.770092758  0           -0.001243607 -0.555405551  0.001144285 -0.464975616 -0.000207365 -0.710919477 0.14062 0.228563922 0.689143919 0.448423418 0.3926 0.3717
    """)

    CONSTANTS = {'c2': 1.06, 'c4': -2.1, 'c4_a': -0.5, 'c8_a': -0.2695, 'c_rb': 50}



"""
Input Variables
M     = Moment Magnitude
T     = Period (sec); Use Period = -1 for PGV computation
             Use 1000 for output the array of Sa with original period
             (no interpolation)
Rrup   = Closest distance (km) to the ruptured plane
eqt    =  type of event
       = 0 interface
       = 1 intra slab
flag       = 0 for the joined Japan & Taiwan
           = 1 for Taiwan
Vs30          = shear wave velocity averaged over top 30 m in m/s
Z1.0 = sediment depth parameter 
Output Variables
Sa: Median spectral acceleration prediction
sigma: logarithmic standard deviation of spectral acceleration
       prediction
tau
phi
"""
def Phung_2020_TWsubGMM(T, M, Ztor, Rrup, Vs30, Z1, flag, eqt):
    % ip = find(period==T);
    % Sa = PLC_SDZ17_sub(M,Ztor,Rrup,Vs30,ip,reg);
    NT=length(T);
    Sa=zeros(1,NT);
    SigT=zeros(1,NT);
    SigSS=zeros(1,NT);
    
    for I=1:1:NT
        T_low = max(period(period <= T(I)));
        T_high = min(period(period >= T(I)));
        ip_low  = find(period==T_low);
        ip_high = find(period==T_high);
        if ( ip_low == ip_high )
            [Sa(I),SigT(I),SigSS(I)]= Phung2020_TWsubGMM(M,Ztor,Rrup,Vs30,Z1,ip_low,flag,eqt);     
        else
            [Sa_low,SigT_low,SigSS_low] = Phung2020_TWsubGMM(M,Ztor,Rrup,Vs30,Z1,ip_low,flag,eqt);
            [Sa_high,SigT_high,SigSS_high] = Phung2020_TWsubGMM(M,Ztor,Rrup,Vs30,Z1,ip_high,flag,eqt);
            
            x = [log(T_low) log(T_high)];
            Y_sa = [log(Sa_low) log(Sa_high)];        
            Y_sigma = [SigSS_low SigSS_high];
            Y_tau = [SigT_low SigT_high];
           
            
            Sa(I) = exp(interp1(x, Y_sa, log(T(I))));
            SigT(I) = interp1(x, Y_sigma, log(T(I)));
            SigSS(I) = interp1(x, Y_tau, log(T(I)));
           
                
        end
    end
    
    return Sa,SigT,SigSS


class PhungEtAl2020SInter(GMPE):

    def get_mean_and_stddevs(M, Ztor, Rrup, Vs30, Z10, ip, flag, eqt):
        pass

    COEFFS = CoeffsTable(sa_damping=5, table="""\
    imt   a1      a1_del       a2          a4           a4_del      a5          a6_jp        a6_tw        a7           a8_jp   a8_tw   a10         a11          a12_jp  a12_tw  a13        a14          b     mref vlin   tau4tj      phiss4tj    phis2s4tj   tau_tw      phiss_tw phis2s_tw
    PGA   4.4234  1.141899742 -1.552846733 0.441987425  0.328613796 0.03849929 -0.006794362 -0.000639314  0.681875399 -0.0075 -0.06276 0.016025291 0.014951807  0.8725  0.9321 -0.0256568 -0.011876681 -1.186 7.68  865.1 0.426469333 0.420489356 0.364038777 0.352252822 0.4130   0.3443
    0.01  4.4415  1.152006702 -1.554174269 0.442328411  0.352192886 0.04033665 -0.006817094 -0.000607826  0.679916748 -0.0083 -0.06296 0.017193978 0.014930723  0.8733  0.9327 -0.0259617 -0.012409284 -1.186 7.68  865.1 0.424670673 0.420220542 0.364065617 0.349216437 0.4126   0.3441
    0.02  4.4657  1.154339185 -1.555152194 0.436082809  0.367677006 0.04190178 -0.006816137 -0.000577165  0.697566565 -0.0083 -0.06325 0.01828222  0.01491224   0.8851  0.9395 -0.0262528 -0.016872732 -1.186 7.68  865.1 0.429099403 0.418935068 0.364403496 0.344782755 0.4113   0.3434
    0.05  4.5788  1.515303155 -1.556049687 0.363261281  0.452541112 0.04509359 -0.007285287 -0.000490096  1.036117503 -0.0212 -0.08865 0.020842842 0.01487185   1.2671  1.2819 -0.0270426 -0.08510905  -1.346 7.71 1053.5 0.477262493 0.419356601 0.417921293 0.355375576 0.4095   0.3907
    0.075 4.7290  1.904431142 -1.554562252 0.319469336  0.513739193 0.04623140 -0.007702243 -0.00042309   1.229932174 -0.0278 -0.09405 0.022162011 0.014854753  1.4426  1.4458 -0.0276048 -0.118005772 -1.471 7.77 1085.7 0.516365961 0.41012804  0.469674634 0.380828528 0.4003   0.4405
    0.1   4.8676  1.945456526 -1.551165488 0.325896968  0.499522237 0.04819708 -0.007674043 -0.000361045  1.534436374 -0.0308 -0.09783 0.022757257 0.014852358  1.5605  1.5761 -0.0280794 -0.171218187 -1.624 7.77 1032.5 0.512863781 0.420066336 0.469076147 0.388526115 0.4094   0.4499
    0.15  5.0388  1.787100626 -1.539140832 0.350561168  0.45427803  0.04325090 -0.00782682  -0.000251542  1.263659339 -0.0193 -0.08546 0.021797461 0.014893477  1.6752  1.7975 -0.0287650 -0.124720279 -1.931 7.78  877.6 0.461620132 0.433030041 0.437340846 0.368100637 0.4280   0.4104
    0.2   5.1375  1.562515125 -1.520764226 0.401101385  0.363869484 0.03692059 -0.007547403 -0.000161014  1.177341019 -0.0087 -0.07070 0.020180594 0.015004213  1.8029  2.0219 -0.0291017 -0.120958201 -2.188 7.72  748.2 0.441284014 0.446059203 0.397161802 0.368643954 0.4438   0.3782
    0.25  5.1106  1.356740101 -1.489051706 0.440779304  0.314270529 0.06597319 -0.007323965 -0.0000890    1.046187707 -0.0062 -0.06045 0.018556649 0.015194298  1.8843  2.2014 -0.0290970 -0.116255248 -2.381 7.62  654.3 0.434871493 0.456165064 0.384511586 0.375291842 0.4503   0.3559
    0.3   5.0573  1.206013896 -1.464118878 0.486141867  0.282854636 0.06197944 -0.006976346 -0.0000354    0.783076472 -0.0045 -0.05366 0.016978648 0.01540766   1.9457  2.3240 -0.0287552 -0.077408811 -2.518 7.54  587.1 0.417105574 0.459407794 0.373773022 0.365828808 0.4532   0.3460
    0.4   4.9001  0.760110718 -1.414761429 0.593885499  0.176621233 0.06979644 -0.006143907  0.0000145    0.56945524   0.0240 -0.01430 0.014555899 0.015952307  2.1491  2.4684 -0.0269993 -0.054966213 -2.657 7.42  503   0.412231943 0.452177558 0.372643333 0.383635154 0.4428   0.3546
    0.5   4.7813  0.431629072 -1.383170353 0.719248494  0.077343234 0.08783791 -0.005504091 -0.0000421    0.437054838  0.0488  0.02962 0.012627818 0.016437613  2.2064  2.4869 -0.0235859 -0.034173086 -2.669 7.38  456.6 0.396422531 0.443446716 0.369406327 0.378521294 0.4383   0.3589
    0.6   4.6503  0.214072689 -1.360022278 0.848115514  0.044354701 0.09612877 -0.004739568 -0.0000726    0.497762038  0.0640  0.06271 0.011191399 0.01652538   2.1559  2.3983 -0.0180673 -0.06069315  -2.599 7.36  430.3 0.403512982 0.4378372   0.397812841 0.369787955 0.4426   0.3812
    0.75  4.3917 -0.01782956  -1.313716982 0.96522535  -0.012346815 0.10612877 -0.004285202 -0.000119483  0.262897537  0.0720  0.08935 0.009211979 0.016212382  1.9770  2.0760 -0.0150673 -0.039053473 -2.401 7.32  410.5 0.409058414 0.446095737 0.419424271 0.375567859 0.4556   0.3856
    1.0   3.7367 -0.204991951 -1.236841977 1.174894012 -0.083175191 0.22744484 -0.003957479 -0.000199116 -0.126754198  0.0791  0.12475 0.006851124 0.015784785  1.4834  1.4846 -0.0031849  0.017806808 -1.955 7.25  400   0.428087961 0.44128784  0.408446403 0.375762655 0.4518   0.3692
    1.5   2.8030 -0.382378342 -1.100570482 1.360979471 -0.226959428 0.16136621 -0.003379651 -0.000362196 -0.121313834  0.0864  0.16430 0.003814084 0.01399451   0.5185  0.3763 -0.0031849 -0.005705423 -1.025 7.25  400   0.440164103 0.42093392  0.420315802 0.39959416  0.4305   0.3703
    2.0   1.8695 -0.352611734 -0.990254902 1.38307024  -0.206168741 0.22767232 -0.003469497 -0.000611716 -0.496676074  0.0905  0.17542 0.001733925 0.011927777 -0.3208 -0.4191 -0.0031849  0.053155037 -0.299 7.25  400   0.451402135 0.425797447 0.416797894 0.411391314 0.4413   0.3713
    2.5   1.0159 -0.228719047 -0.896093506 1.382803719 -0.163340854 0.27153377 -0.003409644 -0.000869846 -0.513466165  0.0976  0.16991 0           0.009749305 -0.6999 -0.7674 -0.0031849  0.068765677  0     7.25  400   0.461009777 0.419978946 0.404296599 0.428877733 0.4379   0.3578
    3.0   0.4461 -0.16534756  -0.818199517 1.391730855 -0.154799226 0.28822087 -0.003614492 -0.00106641  -0.600511124  0.0987  0.16367 0           0.007785629 -0.6077 -0.7527 -0.0031849  0.071577687  0     7.25  400   0.457681279 0.413207757 0.362727332 0.432913094 0.4302   0.3500
    4.0  -0.4692  0.010400184 -0.730697376 1.36799257  -0.112793712 0.32589322 -0.003749858 -0.001185004 -0.425097306  0.0890  0.15060 0           0.00494863  -0.5689 -0.7088 -0.0031849  0.042405486  0     7.25  400   0.470193371 0.36936182  0.354026172 0.435941037 0.4268   0.3234
    5.0  -0.8403  0.135306871 -0.734817372 1.379913313 -0.003105582 0.30383949 -0.003243671 -0.0009885   -0.528599974  0.0758  0.15646 0           0.003408571 -0.4942 -0.7305 -0.0031849  0.054712361  0     7.25  400   0.461834624 0.349936999 0.300771328 0.415321618 0.4286   0.3040
    """)

    CONSTANTS = {'a3': 0.1, 'a9': 0.25, 'c': 1.88, 'c4': 10, 'n': 1.18}
    # regional term
    if jptw:
        a1ip = C['a1'] + C['a1_del']
        a4 = C['a4'] + C['a4_del']

        a6 = C['a6_jp']
        a12ip = C['a12_jp']

        SigSS = C['tau4tj']
        phi_SS = C['phiss4tj']
        phi_S2S = C['phis2s4tj']
    elif tw:
        a1ip = C['a1']
        a4 = C['a4']
        a6 = C['a6']
        a12ip = C['a12']

        SigSS = C['tau4_tw']
        phi_SS = C['phiss4_tw']
        phi_S2S = C['phis2s4_tw']
    # magnitude term
    if mag <= C['mref']:
       fmag =  a4 * (mag - C['mref']) + C['a13'] * (10 - mag) ** 2
    else:
       fmag =  C['a5'] * (mag - C['mref']) + C['a13'] * (10 - mag) ** 2
    # ztor term
    if eqt == 0:
       f_ztor = C['a10'] * (min(ztor, 40) - 20)
    else:
       f_ztor = C['a11'] * (min(ztor, 80) - 40)
    # path term
    if subduction_interface:
        X = a1ip + (C['a2'] + a3 * (mag - 7.8)) * log(rrup + c4 * exp(a9 * (mag - 6))) + a6 * rrup
    elif subduction_intraslab:
        X = a1ip + C['a7'] + (C['a2'] + C['a14'] + a3 * (mag - 7.8)) * log(rrup + c4 * exp(a9 * (mag - 6))) + a6 * rrup
    # PGA at rock with Vs30 = 1000 m/s
    pga_1000 = PGAatrock(eqt, mag, rrup, ztor, 1000)
    # site Effect 
    Vs30 = min(Vs30, 1000);
    # nonlinear component
    if (Vs30 < C['vlin']):
        fsite = a12ip * log(vs30 / C['vlin']) - C['b'] * log(pga_1000 + s['c']) \
            + C['b'] * log(pga_1000 + s['c'] * (vs30/C['vlin']) ** s['n'])
    else:
        fsite = a12ip * log(vs30 / C['vlin']) + C['b'] * s['n'] * log(vs30 / C['vlin'])
    # Basin Depth term
    if tw:
        Ez_1 = exp(-3.96 / 2 * log((vs30 ** 2 + 352.7 ** 2) / (1750 ** 2 + 352.7 ** 2)))
        if np.isnan(Z10):
            f_z10 = 0
        else:
            f_z10 = C['a8'] * (min(log(Z10 / Ez_1), 1))
    elif jptw:
       Ez_1 = exp(-5.23 / 2 * log((vs30 ** 2 + 412.39 ** 2) / (1360 ** 2 + 412.39 ** 2)))
       if np.isnan(Z10):
          f_z10 = 0
       else:
          f_z10 = C['a8_jp'] * (min(log(Z10 / Ez_1), 1))
    # median
    Sa = fmag + X  + f_ztor + fsite + f_z10
    # standard deviation 
    SigT = sqrt(SigSS ** 2 + phi_SS ** 2 + phi_S2S ** 2)
    SigSS = sqrt(SigSS ** 2 + phi_SS ** 2)

    def PGAatrock(self, C_PGA, mag, rrup, ztor, vs30):
        s = self.CONSTANTS
        # magnitude term
        if mag <= C_PGA['mref']:
            fmag =  C_PGA['a4'] \
                * (mag - C_PGA['mref']) + C_PGA['a13'] * (10 - mag) ** 2
        else:
            fmag =  C_PGA['a5'] \
                * (mag - C_PGA['mref']) + C_PGA['a13'] * (10 - mag) ** 2
        # ztor term
        if subduction_interface:
           f_ztor = C_PGA['a10'] * (min(ztor, 40) - 20)
        elif subduction_intraslab:
           f_ztor = C_PGA['a11'] * (min(ztor, 80) - 40)
        # path term
        if subduction_interface:
            X = (C_PGA['a2'] + s['a3'] * (mag - 7.8)) \
                * log(rrup + s['c4'] * exp(s['a9'] * (mag - 6))) \
                + C_PGA['a6'] * rrup
        elif subduction_intraslab:
            X = (C_PGA['a2'] + C_PGA['a14'] + s['a3'] * (mag - 7.8)) \
                * log(rrup + s['c4'] * exp(s['a9'] * (mag - 6))) \
                + C_PGA['a6'] * rrup + C_PGA['a7']
        # site function:
        flinsite =  C_PGA['a12'] * log(vs30 / C_PGA['vlin']) \
            + C_PGA['b'] * s['n'] * log(vs30 / C_PGA['vlin'])
    
        return exp(C_PGA['a1'] + fmag + X +  f_ztor + flinsite);
