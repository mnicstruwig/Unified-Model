import numpy as np
from unified_model.utils.utils import pretty_str


# TODO: Move to utils
def _gradient(f, x, delta_x=1e-3):
    """Compute the gradient of function `f` at point `y` relative to `x`"""
    gradient = (f(x + delta_x) - f(x - delta_x))/(2*delta_x)
    if np.isinf(gradient):
        return 0.0
    return gradient


class ElectricalModel:
    """A model of an electrical system.

    Attributes
    ----------
    name : str
        String identifier of the electrical model.
    flux_model : fun
        Function that returns the flux linkage of a coil when the position of a
        magnet assembly's bottom edge is passed to it.
    coil_resistance: float
        The resistance of the coil in Ohms.
        Default value is `np.inf`, which is equivalent to an open-circuit
        system.
    load_model : obj
        A load model.
    flux_gradient : fun
        The gradient of `flux_model` if the `precompute_gradient` argument is
        set to True when using the `set_flux_model` method. Otherwise, None.

    """

    def __init__(self, name):
        """Constructor

        Parameters
        ----------
        name : str
            String identifier of the electrical model.

        """
        self.name = name
        self.flux_model = None
        self.coil_resistance = np.inf
        self.load_model = None
        self.flux_gradient = None
        self.precompute_gradient = False

    def __str__(self):
        """Return string representation of the ElectricalModel"""
        return "Electrical Model:\n" + pretty_str(self.__dict__)

    def set_flux_model(self, flux_model, dflux_model):
        """Assign a flux model.

        Parameters
        ----------
        flux_model : function
            Function that returns the flux linkage of a coil when the position
            of a magnet assembly's bottom edge is passed to it.
        flux_model : function
            Function that returns the derivative of the flux linkage of a coil
            (relative to `z` i.e. the position of a magnet assembly's bottom
            edge) when the position of a magnet assembly's bottom edge is passed to it.

        """
        self.flux_model = flux_model
        self.dflux_model = dflux_model

    def set_coil_resistance(self, R):
        """Set the resistance of the coil"""
        self.coil_resistance = R

    def set_load_model(self, load_model):
        """Assign a load model

        Parameters
        ----------
        load_model : obj
            The load model to set.

        """
        self.load_model = load_model

    def get_flux_gradient(self, y):
        """Return the instantaneous gradient of the flux relative to z.

        Parameters
        ----------
        y : ndarray
            The `y` input vector that is supplied to the set of governing
            equations, with shape (n,), where `n` is the number of equations
            in the set of governing equations.

        Returns
        -------
        ndarray
            The instantaneous flux gradient.

        """
        x1, x2, x3, x4, x5 = y  # TODO: Remove reliance on hard-coding.
        if self.precompute_gradient is True:
            return self.flux_gradient(x3-x1)
        return _gradient(self.flux_model, x3-x1)

    def get_emf(self, mag_pos, mag_vel):
        """Return the instantaneous emf produced by the electrical system.

        Note, this is the open-circuit emf and *not* the emf supplied to
        the load.

        Parameters
        ----------
        y : ndarray
            The `y` input vector that is supplied to the set of governing
            equations, with shape (n,), where `n` is the number of equations
            in the set of governing equations.

        Returns
        -------
        ndarray
            The instantaneous emf.

        """
        dphi_dz = self.dflux_model(mag_pos)
        emf = dphi_dz * (mag_vel)
        return emf

    def get_current(self, emf_oc):
        """Return the instantaneous current produced by the electrical system.

        Parameters
        ----------
        y : ndarray
            The `y` input vector that is supplied to the set of governing
            equations, with shape (n,), where `n` is the number of equations
            in the set of governing equations.

        Returns
        -------
        ndarray
            The instantaneous current.

        """
        if not self.load_model:
            return 0

        r_load = self.load_model.R
        r_coil = self.coil_resistance

        v_load = emf_oc * r_load / (r_load + r_coil)
        return v_load / r_load
