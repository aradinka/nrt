"""Fitting stable models

Functions defined in this module always use a 2D array containing the dependant
variables (y) and return coefficient (beta), residuals matrices as well as
a boolean mask indicating which variables aren't stable.
These functions are meant to be called in ``nrt.BaseNrt._fit()``

Citations:

- Zhu, Zhe, and Curtis E. Woodcock. 2014. “Continuous Change Detection and
Classification of Land Cover Using All Available Landsat Data.” Remote
Sensing of Environment 144 (March): 152–71.
https://doi.org/10.1016/j.rse.2014.01.011.
"""
import numpy as np
import numba

from nrt.fit_methods import ols
from nrt.log import logger


def ccdc_stable_fit(X, y, dates, threshold=3, **kwargs):
    """Fitting stable regressions using an adapted CCDC method

    Models are first fit using OLS regression. Those models are then checked for
    stability with 'is_stable_ccdc()'. If a model is not stable, the two oldest
    acquisitions are removed, a model is fit using this shorter
    time-series and again checked for stability. This process continues as long
    as all of the following 3 conditions are met:

    1. There are unstable timeseries left.
    2. There are enough cloud-free acquisitions left (threshold is 1.5x the
        number of parameters in the design matrix).
    3. There is still data of more than 1 year available.

    Args:
        X ((M, N) np.ndarray): Matrix of independant variables
        y ((M, K) np.ndarray): Matrix of dependant variables
        dates ((M, ) np.ndarray): Corresponding dates to y in numpy datetime64
        threshold (float): Sensitivity of stability checking. Gets passed to
            ``is_stable_ccdc()``
    Returns:
        beta (numpy.ndarray): The array of regression estimators
        residuals (numpy.ndarray): The array of residuals
        is_stable (numpy.ndarray): 1D Boolean array indicating stability
    """
    # 0. Remove observations with too little data
    # Minimum 1.5 times the number of coefficients
    obs_count = np.count_nonzero(~np.isnan(y), axis=0)
    enough = obs_count > X.shape[1] * 1.5
    is_stable = np.full(enough.shape, False, dtype=np.bool)
    y_sub = y[:, enough]
    X_sub = X

    # Initialize dates to check if there's acquisitions for an entire year
    first_date = dates[0]
    last_date = dates[-1]
    delta = last_date - first_date

    # If the dates are less than one year apart Raise an Exception
    if delta.astype('timedelta64[Y]') < np.timedelta64(1, 'Y'):
        raise ValueError('"dates" requires a full year of data.')

    # Initialize beta and residuals filled with nan
    beta = np.full([X.shape[1], y.shape[1]], np.nan, dtype=np.float32)
    residuals = np.full(y.shape, np.nan, dtype=np.float32)

    # Keep going while everything isn't either stable or has enough data left
    while not np.all(is_stable | ~enough):
        # 1. Fit
        beta_sub, residuals_sub = ols(X_sub, y_sub)
        beta[:,~is_stable & enough] = beta_sub
        residuals[:,~is_stable & enough] = np.nan
        residuals[-y_sub.shape[0]:,~is_stable & enough] = residuals_sub

        # 2. Check stability
        is_stable_sub = is_stable_ccdc(beta_sub[1, :], residuals_sub, threshold)

        # 3. Update mask
        # Everything that wasn't stable last time and had enough data gets updated
        is_stable[~is_stable & enough] = is_stable_sub

        # 4. Change Timeframe and remove everything that is now stable
        y_sub = y_sub[2:,~is_stable_sub]
        X_sub = X_sub[2:,:]
        logger.debug('Fitted %d stable pixels.',
                     is_stable_sub.shape[0]-y_sub.shape[1])
        dates = dates[2:]
        first_date = dates[0]
        delta = last_date - first_date

        # If the dates are less than one year apart stop the loop
        if delta.astype('timedelta64[Y]') < np.timedelta64(1, 'Y'):
            break
        # Check where there isn't enough data left
        obs_count = np.count_nonzero(~np.isnan(y_sub), axis=0)
        enough_sub = obs_count > X.shape[1] * 1.5
        enough[~is_stable & enough] = enough_sub
        # Remove everything where there isn't enough data
        y_sub = y_sub[:,enough_sub]
    return beta, residuals, is_stable


def is_stable_ccdc(slope, residuals, threshold):
    """Check the stability of the fitted model using CCDC Method

    Stability is given if:
        1.             slope / RMSE < threshold
        2. first observation / RMSE < threshold
        3.  last observation / RMSE < threshold

    For multiple bands Zhu et al. 2014 proposed the mean of all bands to
    be > 1 to signal instability.

    Args:
        slope (np.ndarray): 1D slope/trend of coefficients
        residuals (np.ndarray): 2D corresponding residuals
        threshold (float): threshold value to signal change

    Returns:
        np.ndarray: 1D boolean array with True = stable
    """
    # TODO check if SWIR and Green are the same size
    # "flat" 2D implementation
    rmse = np.sqrt(np.nanmean(residuals ** 2, axis=0))
    slope_rmse = slope / rmse < threshold
    first = residuals[0, :] / rmse < threshold
    last = residuals[-1, :] / rmse < threshold
    # It's only stable if all conditions are met
    is_stable = slope_rmse & first & last
    return is_stable


#@numba.jit(nopython=True, nogil=True)
def recresid(X, y, span):
    nobs, nvars = X.shape

    recresid_ = np.nan * np.zeros((nobs))
    recvar = np.nan * np.zeros((nobs))

    X0 = X[:span, :]
    y0 = y[:span]

    # Initial fit
    XTX_j = np.linalg.inv(np.dot(X0.T, X0))
    XTY = np.dot(X0.T, y0)
    beta = np.dot(XTX_j, XTY)

    yhat_j = np.dot(X[span - 1, :], beta)
    recresid_[span - 1] = y[span - 1] - yhat_j
    recvar[span - 1] = 1 + np.dot(X[span - 1, :],
                                  np.dot(XTX_j, X[span - 1, :]))
    for j in range(span, nobs):
        x_j = X[j:j+1, :]
        y_j = y[j]

        # Prediction with previous beta
        resid_j = y_j - np.dot(x_j, beta)

        # Update
        XTXx_j = np.dot(XTX_j, x_j.T)
        f_t = 1 + np.dot(x_j, XTXx_j)
        XTX_j = XTX_j - np.dot(XTXx_j, XTXx_j.T) / f_t  # eqn 5.5.15

        beta = beta + (XTXx_j * resid_j / f_t).ravel()  # eqn 5.5.14
        recresid_[j] = resid_j.item()
        recvar[j] = f_t.item()

    return recresid_ / np.sqrt(recvar)
