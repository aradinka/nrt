"""Removing outliers

Functions defined in this module always use a 2D array containing the dependant
variables (y) and return y with outliers set to np.nan.
These functions are meant to be called in ``nrt.BaseNrt._fit()``

Citations:

- Brooks, E.B., Wynne, R.H., Thomas, V.A., Blinn, C.E. and Coulston, J.W., 2013.
  On-the-fly massively multitemporal change detection using statistical quality
  control charts and Landsat data. IEEE Transactions on Geoscience and Remote Sensing,
  52(6), pp.3316-3332.

- Zhu, Zhe, and Curtis E. Woodcock. 2014. “Continuous Change Detection and
  Classification of Land Cover Using All Available Landsat Data.” Remote
  Sensing of Environment 144 (March): 152–71.
  https://doi.org/10.1016/j.rse.2014.01.011.
"""
import numpy as np

from nrt.fit_methods import rirls, ols
from nrt.log import logger


def shewhart(X, y, L):
    """Remove outliers using a Shewhart control chart

    As described in Brooks et al. 2014, following an initial OLS fit, outliers are
    identified using a shewhart control chart and removed.

    Args:
        X ((M, N) np.ndarray): Matrix of independant variables
        y ({(M,), (M, K)} np.ndarray): Matrix of dependant variables
        L (float): control limit used for outlier filtering. Must be a positive
            float. Lower values indicate stricter filtering

    Returns:
        y(np.ndarray): Dependant variables with outliers set to np.nan
    """
    beta_full, residuals_full = ols(X, y)
    # Shewhart chart to get rid of outliers (clouds etc)
    sigma = np.nanstd(residuals_full, axis=0)
    shewhart_mask = np.abs(residuals_full) > L * sigma
    y[shewhart_mask] = np.nan
    return y


def ccdc_rirls(X, y, green, swir, scaling_factor=1, **kwargs):
    """Screen for missed clouds and other outliers using green and SWIR band

    Args:
        X ((M, N) np.ndarray): Matrix of independant variables
        y ((M, K) np.ndarray): Matrix of dependant variables
        green (np.ndarray): 2D array containing spectral values
        swir (np.ndarray): 2D array containing spectral values (~1.55-1.75um)
        scaling_factor (int): Scaling factor to bring green and swir values
            to reflectance values between 0 and 1
        **kwargs: arguments to be passed to fit_methods.rirls()

    Returns:
        np.ndarray: 2D (flat) boolean array with True = clear
    """
    # 1. estimate time series model using rirls for green and swir
    # TODO: change handling so that green and swir are extracted from the
    #       DataArray further up the chain
    shape = green.shape
    shape_flat = (shape[0], shape[1] * shape[2])
    green_flat = green.values.astype(np.float32).reshape(shape_flat)
    swir_flat = swir.values.astype(np.float32).reshape(shape_flat)
    # TODO could be sped up, since masking is the same for green and swir
    g_beta, g_residuals = rirls(X, green_flat, **kwargs)
    s_beta, s_residuals = rirls(X, swir_flat, **kwargs)
    # Update mask using thresholds
    is_outlier = np.logical_or(g_residuals > 0.04*scaling_factor,
                               s_residuals < -0.04*scaling_factor)
    y[is_outlier] = np.nan

    logger.debug('%.2f%% of (non nan) pixels removed.',
                 (np.count_nonzero(is_outlier)
                  / np.count_nonzero(~np.isnan(green)))*100)
    return y
