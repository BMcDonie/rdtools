''' Energy Normalization Module

This module contains functions to help normalize AC energy output with measured
poa_global in preparation for calculating PV system degradation.
'''

import pandas as pd
import pvlib


def pvwatts_dc_power(poa_global, P_stc, T_cell=None,
                     G_stc=1000, T_stc=25, gamma_pdc=None):
    '''
    PVWatts v5 Module Model: DC power given effective poa poa_global, module
    nameplate power, and cell temperature. This function differs from the PVLIB
    implementation by allowing cell temperature to be an optional parameter.

    Note: If T_cell and gamma_pdc are omitted, the temperature term will be
          ignored.

    Parameters
    ----------
    poa_global: Pandas Series (numeric)
        Total effective plane of array irradiance.
    P_stc: numeric
        Module nameplate power at standard test condition.
    T_cell: Pandas Series (numeric)
        Measured or derived cell temperature [degrees celsius].
        Time series assumed to be same frequency as poa_global.
    G_stc: numeric, default value is 1000
        Reference irradiance at standard test condition [W/m**2].
    T_stc: numeric, default value is 25
        Reference temperature at standard test condition [degrees celsius].
    gamma_pdc: numeric, default is None
        Linear array efficiency temperature coefficient [1 / degree celsius].

    Returns
    -------
    dc_power: Pandas Series (numeric)
        DC power determined by PVWatts v5 equation.
    '''

    dc_power = P_stc * poa_global / G_stc

    if T_cell is not None and gamma_pdc is not None:
        temperature_factor = 1 + gamma_pdc*(T_cell - T_stc)
        dc_power = dc_power * temperature_factor

    return dc_power


def normalize_with_pvwatts(energy, pvwatts_kws):
    '''
    Normalize system AC energy output given measured poa_global and
    meteorological data. This method uses the PVWatts V5 module model.

    Energy timeseries and poa_global timeseries can be different granularities.

    Parameters
    ----------
    energy: Pandas Series (numeric)
        Energy time series to be normalized.
    pvwatts_kws: dictionary
        Dictionary of parameters used in the pvwatts_dc_power function.

        PVWatts Parameters
        ------------------
        poa_global: Pandas Series (numeric)
            Total effective plane of array irradiance.
        P_stc: numeric
            Module nameplate power at standard test condition.
        T_cell: Pandas Series (numeric)
            Measured or derived cell temperature [degrees celsius].
            Time series assumed to be same frequency as poa_global.
        G_stc: numeric, default value is 1000
            Reference irradiance at standard test condition [W/m**2].
        T_stc: numeric, default value is 25
            Reference temperature at standard test condition [degrees celsius].
        gamma_pdc: numeric, default is None
            Linear array efficiency temperature coefficient [1 / degree celsius].

    Returns
    -------
    normalized_energy: Pandas Series (numeric)
        Energy divided by Sandia Model DC energy.
    '''

    if energy.index.freq is None:
        freq = pd.infer_freq(energy.index)
    else:
        freq = energy.index.freq

    dc_power = pvwatts_dc_power(**pvwatts_kws)

    energy_dc = dc_power.resample(freq).sum()
    normalized_energy = energy / energy_dc

    return normalized_energy


def sapm_dc_power(pvlib_pvsystem, poa_global):
    '''
    Use Sandia Array Performance Model (SAPM) to compute
    the effective DC power using measured poa_global, ambient temperature, and
    wind speed.

    Parameters
    ----------
    pvlib_pvsystem: pvlib-python LocalizedPVSystem object
        Object contains orientation, geographic coordinates, equipment
        constants.
    poa_global: Pandas DataFrame (numeric)
        Measured poa_global components, ambient temperature, and wind speed.

    Returns
    -------
    dc_power: Pandas Series (numeric)
        DC power derived using Sandia Array Performance Model.
    '''

    solar_position = pvlib_pvsystem.get_solarposition(poa_global.index)

    total_irradiance = pvlib_pvsystem\
        .get_poa_global(solar_position['zenith'],
                        solar_position['azimuth'],
                        poa_global['DNI'],
                        poa_global['GHI'],
                        poa_global['DHI'])

    aoi = pvlib_pvsystem.get_aoi(solar_position['zenith'],
                                 solar_position['azimuth'])

    airmass = pvlib_pvsystem\
        .get_airmass(solar_position=solar_position, model='kastenyoung1989')
    airmass_absolute = airmass['airmass_absolute']

    effective_poa = pvlib.pvsystem\
        .sapm_effective_poa_global(poa_direct=total_irradiance['poa_direct'],
                                   poa_diffuse=total_irradiance['poa_diffuse'],
                                   airmass_absolute=airmass_absolute,
                                   aoi=aoi,
                                   module=pvlib_pvsystem.module,
                                   reference_poa_global=1)

    temp_cell = pvlib_pvsystem\
        .sapm_celltemp(irrad=total_irradiance['poa_global'],
                       wind=poa_global['Wind Speed'],
                       temp=poa_global['Temperature'])

    dc_power = pvlib_pvsystem\
        .pvwatts_dc(g_poa_effective=effective_poa,
                    temp_cell=temp_cell['temp_cell'])

    return dc_power


def normalize_with_sapm(energy, sapm_kws):
    '''
    Normalize system AC energy output given measured poa_global and
    meteorological data. This method relies on the Sandia Array Performance
    Model (SAPM) to compute the effective DC energy using measured poa_global,
    ambient temperature, and wind speed.

    Energy timeseries and poa_global timeseries can be different granularities.

    Parameters
    ----------
    energy: Pandas Series (numeric)
        Energy time series to be normalized.
    sapm_kws: dictionary
        Dictionary of parameters required for sapm_dc_power function.

        SAPM Parameters
        ---------------
        pvlib_pvsystem: pvlib-python LocalizedPVSystem object
            Object contains orientation, geographic coordinates, equipment
            constants.
        poa_global: Pandas DataFrame (numeric)
            Measured poa_global, ambient temperature, and wind speed.

    Returns
    -------
    normalized_energy: Pandas Series (numeric)
        Energy divided by Sandia Model DC energy.
    '''

    if energy.index.freq is None:
        freq = pd.infer_freq(energy.index)
    else:
        freq = energy.index.freq

    dc_power = sapm_dc_power(**sapm_kws)

    energy_dc = dc_power.resample(freq).sum()
    normalized_energy = energy / energy_dc

    return normalized_energy