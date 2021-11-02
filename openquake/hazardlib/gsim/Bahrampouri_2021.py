#!/usr/bin/env python
# coding: utf-8

# In[2]:


"""
Module exports :class:`BahrampouriEtAl2021`,
class:`BahrampouriEtAl2021Asc`,
class:`BahrampouriEtAl2021SSlab`,
class:`BahrampouriEtAl2021SInter`,
"""
import numpy as np
from openquake.hazardlib.gsim.base import GMPE, CoeffsTable
from openquake.hazardlib import const
from openquake.hazardlib.imt import IA


import pandas


def _compute_magnitude(ctx, C):
    
    """
    Compute the source term described in Eq. 7 for ASC and 9 for subduction:
    `` a1 + a2 * M + a3 * max(M - a4, 0) + a7 * ln(Ztor + 1)------ASC
        a1 + a2 * M + a3 * max (M - a4, 0) + a5 * max(M - a6, 0) + a7 * ln(Ztor + 1) + a8 * Finter-------Subduction``
        
        Finter = 0 (subduction interslab)
        Finter = 1 (subduction interface)
    """
    if trt == const.TRT.ACTIVE_SHALLOW_CRUST:
        fsource = C['a1'] + (C['a2'] * ctx.mag) + (C['a3'] * max((ctx.mag - C['a4']),0 )) + (C['a7'] * np.log((ctx.ztor)+1))
        
    else:
        if trt == const.TRT.SUBDUCTION_INTERFACE:
            Finter = 1
        elif trt == const.TRT.SUBDUCTION_INTERSLAB:
            Finter = 0
        fsource = C['a1'] + (C['a2'] * ctx.mag) + (C['a3'] * max((ctx.mag - C['a4']),0 )) +(C['a5'] * max((ctx.mag - C['a6']),0 ))+ (C['a7'] * np.log((ctx.ztor)+1)) +(C['a8'] * Finter)
    return fsource


# In[4]:


def _get_source_saturation_term (ctx, C):
    """
    compute the near source saturation as described in Eq. 11. This is common for all the TRTs
    ``h = b5 +b6*(M-b7)..... M<=b7
    h = b9 + b10*(M - b7)+b11*(M - b7)**2+b12*(M - b7)**3 ...b7< M <= b8
    h = b13 + b14*(M - b8).....M>b8``
    """
    if ctx.mag <= C['b7']:
        h = C['b5'] + C['b6'] * (ctx.mag-C['b7'])
    elif ctx.mag < C['b7'] and ctx.mag <= C['b8']:
        h = C['b9'] + (C['b10']*(ctx.mag-C['b7']))+(C['b11']*(ctx.mag-C['b7'])**2) + (C['b12']*(ctx.mag-C['b7'])**3)
    else:
        h = C['b13'] + (C['b14'] * (ctx.mag - C['b8']))
        
    return h
    


# In[5]:


def _get_site_term(ctx, C):
    """
    compute site scaling as described in Eq.12
    Fsite = c1*ln(vs30)

    """
    fsite = C['C1']*np.log(ctx.vs30)
    return fsite


# In[6]:


def _get_stddevs(C):
    """
    The authors have provided the values of sigma = np.sqrt(tau**2+phi_ss**2+phi_s2s**2)
    
    The within event term (phi) has been calculated by combining the phi_ss and phi_s2s
    """
    sig = C['sig']
    tau = C['tau']
    phi = np.sqrt(C['phi_ss']**2 +C['phi_s2s']**2)
    return sig, tau, phi


# In[1]:


def _get_distance_params(ctx):
    """
    The model requires rrup_f, rrup_b in addition to rrup. 
    The code provided by the authors calculate Rrup_f = Rrup - Rrup_b. 
    In OQ, xvf param is available. Hence, the same param is used.
    """
    if ctx.xvf < 0:
        rrup_b = ctx.xvf
        rrup_f = ctx.rrup - abs(ctx.xvf)
    else:
        rrup_b = 0
        rrup_f = ctx.rrup
    
    return rrup_f, rrup_b
    


# In[10]:


def _compute_distance(ctx, C):
    """
    fpath = b1 * ln(sqrt(rrup^2+(10^h)^2)) + b3b * Rrupb + b3f * Rrupf + b4m * cm + b4k * ck ---ASC
    fpath = (b1 +b2*Finter)*ln(sqrt(rrup^2+(10^h)^2))+ b3b * Rrupb + b3f * Rrupf + b4m * cm + b4k * ck ---subduction
    f = forearc
    b = backarc
    Cm is 1 if the path from the source to the site crosses the volcanic front in Honshu and
    Hokkaido and 0 otherwise; 
    CK is 1 if the path from the source to the site crosses the volcanic 
    front in Kyushu and 0 otherwise;
    """
    cm = 0 # temporary fix
    ck = 0 # temporary fix
    if trt == const.TRT.ACTIVE_SHALLOW_CRUST:
            fpath = C['b1']*(np.log(np.sqrt((ctx.rrup**2) + ((10**h)**2)))) + C['b3b'] * _get_distance_params(ctx)[0] + C['b3f'] * _get_distance_params(ctx)[1] + C['b4m']*cm + C['b4k']*ck

    else: 
        if trt == const.TRT.SUBDUCTION_INTERFACE:
            Finter = 1
        elif trt == const.TRT.SUBDUCTION_INTERSLAB:
            Finter = 0

            fpath = (C['b1'] + C['b2']*Finter) * (np.log(np.sqrt((ctx.rrup**2) + ((10**h)**2)))) + C['b3b'] * _get_distance_params(ctx)[0] + C['b3f'] * _get_distance_params(ctx)[1] + C['b4m']*cm + C['b4k']*ck
    
    return fpath


# In[11]:


def _get_arias_intensity_term(ctx, C):
    """
    Implementing Eq. 6
    """
    ia_1 = _compute_magnitude(ctx, C) + _compute_distance (ctx, C) + _get_site_term (ctx, C)
    return ia_l


# In[12]:


def _get_arias_intensity_additional_term(ctx, C):
    """
    the second term in Eq. 5 is computed
    
    """
    ia_2 = C['c2']*(np.exp(C['c3']*(min(ctx.vs30, 1100)-280)) - np.exp(C['C3']*(1100-280))) * np.log((np.exp(ia_l)+C['c4'])/C['c4'])
    return ia_2


# In[41]:


class BahrampouriEtAl2021Asc(GMPE):
    """
    Implements GMPE by Mahdi Bahrampouri, Adrian Rodriguez-Marek and Russell A Green 
    developed from the Kiban-Kyoshin network (KiK)-net database. This GMPE is specifically derived
    for arias intensity. This GMPE is described in a paper
    published in 2021 on Earthquake Spectra, Volume 37, Pg 428-448 and
    titled 'Ground motion prediction equations for Arias Intensity using the Kik-net database'.
    """
    #: Supported tectonic region type is active shallow crust
    DEFINED_FOR_TECTONIC_REGION_TYPE = const.TRT.ACTIVE_SHALLOW_CRUST

    #: Supported intensity measure types are areas intensity
    DEFINED_FOR_INTENSITY_MEASURE_TYPES = {IA}

    #: Supported intensity measure component is geometric mean
    DEFINED_FOR_INTENSITY_MEASURE_COMPONENT = const.IMC.MEDIAN_HORIZONTAL

    #: Supported standard deviation types are inter-event, intra-event
    #: and total, see paragraph "Equations for standard deviations", page
    #: 1046.
    DEFINED_FOR_STANDARD_DEVIATION_TYPES = {
        const.StdDev.TOTAL, const.StdDev.INTER_EVENT, const.StdDev.INTRA_EVENT}

    #: Required site parameters are Vs30 and xvf
    REQUIRES_SITES_PARAMETERS = {'vs30','xvf'}

    #: Required rupture parameters are magnitude,ztor
   
    REQUIRES_RUPTURE_PARAMETERS = {'mag','ztor'}

    #: Required distance measures are Rrup (see Table 2,
    #: page 1031).
    REQUIRES_DISTANCES = {'rrup',}
    
    
    def compute(self, ctx, imts, mean, sig, tau, phi):
        """
        See :meth:`superclass method
        <.base.GroundShakingIntensityModel.compute>`
        for spec of input and result values.
        """
        for m, imt in enumerate(imts):
            C = self.COEFFS[imt]
            # Implements mean model (equation 12)
            mean[m] = np.exp((_get_arias_intensity_term (ctx, C) + _get_arias_intensity_additional_term (ctx, C)))

            sig[m], tau[m], phi[m] = _get_stddevs(C)

    #: For Ia, coefficients are taken from table 3
    COEFFS = CoeffsTable(sa_damping=5, table="""    IMT      a1     a2      a3    a4    a7     b1      b3b    b3f     b4m     b4k      b5    b6   b7   b8     b9    b10    b11     b12     b13   b14     c1      c2      c3    c4   phi_ss    tau    phi_s2s   sig
    ia    -4.2777 2.9352 -2.3986 7.0 0.7008 -2.8299 -0.0039 -0.0016 -0.6542 -0.2876 0.7497 0.43 5.744 7.744 0.7497 0.43 -0.0488 -0.08312 1.4147 0.235 -1.1076 -0.3607 -0.0077 0.35 0.761585 0.77617 0.840053 1.374096
    """)


# In[42]:


class BahrampouriEtAl2021SInter(GMPE):
    """
    Implements GMPE by Mahdi Bahrampouri, Adrian Rodriguez-Marek and Russell A Green 
    developed from the Kiban-Kyoshin network (KiK)-net database. This GMPE is specifically derived
    for arias intensity. This GMPE is described in a paper
    published in 2021 on Earthquake Spectra, Volume 37, Pg 428-448 and
    titled 'Ground motion prediction equations for Arias Intensity using the Kik-net database'.
    """
    #: Supported tectonic region type is SUBDUCTION INTERFACE, see title!
    DEFINED_FOR_TECTONIC_REGION_TYPE = const.TRT.SUBDUCTION_INTERFACE

    #: Supported intensity measure types are areas intensity
    DEFINED_FOR_INTENSITY_MEASURE_TYPES = {IA}

    #: Supported intensity measure component is geometric mean
    DEFINED_FOR_INTENSITY_MEASURE_COMPONENT = const.IMC.MEDIAN_HORIZONTAL

    #: Supported standard deviation types are inter-event, intra-event
    #: and total, see paragraph "Equations for standard deviations", page
    #: 1046.
    DEFINED_FOR_STANDARD_DEVIATION_TYPES = {
        const.StdDev.TOTAL, const.StdDev.INTER_EVENT, const.StdDev.INTRA_EVENT}

    #: Required site parameters are Vs30 and xvf
    REQUIRES_SITES_PARAMETERS = {'vs30','xvf'}

    #: Required rupture parameters are magnitude,ztor
   
    REQUIRES_RUPTURE_PARAMETERS = {'mag','ztor'}

    #: Required distance measures are Rrup (see Table 2,
    #: page 1031).
    REQUIRES_DISTANCES = {'rrup',}
    
    ## Applicable range of the model
    APPLICABLE_RANGE = {'mag': np.arange(4.0,9.1, 0.1)}
    if mag < 5.0:
        APPLICABLE_RANGE['dist'] = np.arange(0,100,1)
    elif mag > 7.0:
        APPLICABLE_RANGE['dist'] = np.arange(0,1001,1)
    else: 
        APPLICABLE_RANGE['dist'] = np.arange(100,1001,1)
    
    
    def compute(self, ctx, imts, mean, sig, tau, phi):
        """
        See :meth:`superclass method
        <.base.GroundShakingIntensityModel.compute>`
        for spec of input and result values.
        """
        for m, imt in enumerate(imts):
            C = self.COEFFS[imt]
            # Implements mean model (equation 12)
            mean[m] = np.exp((_get_arias_intensity_term (ctx, C) + _get_arias_intensity_additional_term (ctx, C)))

            sig[m], tau[m], phi[m] = _get_stddevs(C)

    #: For Ia, coefficients are taken from table 3
    COEFFS = CoeffsTable(sa_damping=5, table="""    IMT      a1      a2      a3   a4      a5     a6    a7      a8      b1      b2      b3b      b3f      b4m      b4k      b5      b6    b7      b8    b9      b10      b11      b12    b13     b14      c1      c2      c3      c4      phi_ss   tau     phi_s2s    sig
    ia    -0.6169  2.5269  1.531  6.5  -3.2923  7.5  0.5462  0.6249  -2.7534  -0.2816  -0.0044  -0.003  -1.2608  -0.2992  0.7497  0.43  5.744  7.744  0.7497  0.43  -0.0488  -0.08312  1.4147  0.235  -1.3763  -0.1003  -0.0069  0.356  0.73761  0.92179  1.12747  1.632469
    """)


# In[43]:


class BahrampouriEtAl2021SSlab(GMPE):
    """
    Implements GMPE by Mahdi Bahrampouri, Adrian Rodriguez-Marek and Russell A Green 
    developed from the Kiban-Kyoshin network (KiK)-net database. This GMPE is specifically derived
    for arias intensity. This GMPE is described in a paper
    published in 2021 on Earthquake Spectra, Volume 37, Pg 428-448 and
    titled 'Ground motion prediction equations for Arias Intensity using the Kik-net database'.
    """
    #: Supported tectonic region type is SUBDUCTION INTERFACE, see title!
    DEFINED_FOR_TECTONIC_REGION_TYPE = const.TRT.SUBDUCTION_INTRASLAB

    #: Supported intensity measure types are areas intensity
    DEFINED_FOR_INTENSITY_MEASURE_TYPES = {IA}

    #: Supported intensity measure component is geometric mean
    DEFINED_FOR_INTENSITY_MEASURE_COMPONENT = const.IMC.MEDIAN_HORIZONTAL

    #: Supported standard deviation types are inter-event, intra-event
    #: and total, see paragraph "Equations for standard deviations", page
    #: 1046.
    DEFINED_FOR_STANDARD_DEVIATION_TYPES = {
        const.StdDev.TOTAL, const.StdDev.INTER_EVENT, const.StdDev.INTRA_EVENT}

    #: Required site parameters are Vs30 and xvf
    REQUIRES_SITES_PARAMETERS = {'vs30','xvf'}

    #: Required rupture parameters are magnitude,ztor
   
    REQUIRES_RUPTURE_PARAMETERS = {'mag','ztor'}

    #: Required distance measures are Rrup (see Table 2,
    #: page 1031).
    REQUIRES_DISTANCES = {'rrup',}
    
    def compute(self, ctx, imts, mean, sig, tau, phi):
        """
        See :meth:`superclass method
        <.base.GroundShakingIntensityModel.compute>`
        for spec of input and result values.
        """
        for m, imt in enumerate(imts):
            C = self.COEFFS[imt]
            # Implements mean model (equation 12)
            mean[m] = np.exp((_get_arias_intensity_term (ctx, C) + _get_arias_intensity_additional_term (ctx, C)))

            sig[m], tau[m], phi[m] = _get_stddevs(C)

    #: For Ia, coefficients are taken from table 3
    COEFFS = CoeffsTable(sa_damping=5, table="""    IMT      a1      a2      a3   a4      a5     a6    a7      a8      b1      b2      b3b      b3f      b4m      b4k      b5      b6    b7      b8    b9      b10      b11      b12    b13     b14      c1      c2      c3      c4      phi_ss   tau     phi_s2s    sig
    ia    -0.6169  2.5269  1.531  6.5  -3.2923  7.5  0.5462  0.6249  -2.7534  -0.2816  -0.0044  -0.003  -1.2608  -0.2992  0.7497  0.43  5.744  7.744  0.7497  0.43  -0.0488  -0.08312  1.4147  0.235  -1.3763  -0.1003  -0.0069  0.356  0.73761  0.92179  1.12747  1.632469
    """)