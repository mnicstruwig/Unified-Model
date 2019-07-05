import pandas as pd

from unified_model.electrical_system.flux.model import flux_interpolate, flux_univariate_spline
from unified_model.utils.utils import fetch_key_from_dictionary


def _parse_raw_flux_input(raw_flux_input):
    """Parse a raw flux input.

    Supports either a pandas dataframe, or a .csv file.

    Parameters
    ----------
    raw_flux_input : string or pandas dataframe
        A string referencing the .csv file to load or a pandas dataframe that
        will be loaded directly.

    Returns
    -------
    pandas dataframe
        Pandas dataframe containing the raw flux input.

    """
    if isinstance(raw_flux_input, str):
        return pd.read_csv(raw_flux_input)
    if isinstance(raw_flux_input, pd.DataFrame):
        return raw_flux_input


class FluxDatabase(object):
    """Convert .csv produced by Maxwell parametric simulation into a flux database.

    Attributes
    ----------
    raw_database : pandas dataframe
        Pandas dataframe containing the raw loaded .csv as exported by ANSYS
        Maxwell
    velocity : float
        Velocity in m/s of the moving magnet as specified in the ANSYS Maxwell
        simulation.
    lut : dict
        Lookup table used internally to map parameters to keys. Should not be
        accessed or modified by the user.
    database : dict
        Internal database that, in conjunction with `lut` is used to store the
        flux data.

    """

    def __init__(self, csv_database_path, fixed_velocity):
        """Initialize the FluxDatabase

        Parameters
        ----------
        csv_database_path : str
            Path to the raw .csv file exported from ANSYS Maxwell.
        fixed_velocity : float
            Velocity in m/s of the moving magnet as specified in the ANSYS
            Maxwell simulation.

        """

        self.raw_database = pd.read_csv(csv_database_path)
        self.velocity = fixed_velocity
        self.lut = None
        self.database = {}
        self._produce_database()

    @staticmethod
    def _extract_parameter_from_str(str_):
        """Extract parameters from a string generated by ANSYS Maxwell

        Parameters
        ----------
        str_ : str
            String generated by ANSYS Maxwell when exporting a parametric
            simulation. Typically found as a field heading in the
            exported .csv file.

        Returns
        -------
        dict
            Dictionary containing the parameter name and parameter values as
            key-value pairs.

        """
        split_ = str_.split()
        unprocessed_params = [s for s in split_ if '=' in s]
        param_names = [param.split('=')[0] for param in unprocessed_params]
        param_values = [param.split('=')[1].replace("'", '') for param in unprocessed_params]

        param_dict = {}
        for name, value in zip(param_names, param_values):
            param_dict[name] = value
        return param_dict

    def _produce_database(self):
        """Build the flux database."""

        # TODO: Put in separate preprocessing function
        self.time = self.raw_database.iloc[:, 0].values/1000
        self.z = self.time * self.velocity

        self._create_index(self._extract_parameter_from_str(self.raw_database.columns[1]).keys())

        # Add flux curves to database
        for col in self.raw_database.columns[1:]:  # First column is time info
            key_dict = self._extract_parameter_from_str(col)
            self.add(key_dict, value=self.raw_database[col].values)

    def _make_db_key(self, **kwargs):
        """Build a database key using the internal look-up table."""
        db_key = [None]*len(self.lut)
        for key in kwargs:
            db_key[self.lut[key]] = kwargs[key]
        if None in db_key:
            raise KeyError('Not all keys specified')
        return tuple(db_key)

    def add(self, key_dict, value):
        """Add an entry to the database.

        This method should preferably not be used to build the original
        database, and should instead be used to add once-off or the odd
        additional sample to a database that has been built from a .csv file
        exported by ANSYS Maxwell.

        Parameters
        ----------
        key_dict : dict
            Key-value pairs to be used as the lookup for `value`. All keys
            must be used when performing lookup, i.e. if multiple keys are
            specified in `key_dict`, multiple keys must be used for the lookup
            of `value`.
        value :
            Any data structure to store in the database. Accessible using
            the `query` method.

        Returns
        -------
        None

        Example
        -------
        >>> key_dict = {'param_1' : param_1_value, 'param_2': param_2_value)
        >>> value = np.ones(3)
        >>> my_flux_database.add(key_dict, value)
        >>> my_flux_database.query(param_1=param_1_value, param_2=param_2_value)
        array([1, 1, 1])

        """
        db_key = self._make_db_key(**key_dict)
        self.database[db_key] = value

    def query_to_model(self, flux_model_type, coil_center, mm, **kwargs):
        """Query the database and return a flux model.

        This is intended to be a convenience function. It works identically
        to the `query` method, but returns a flux model instead of the actual
        flux curve.

        Parameters
        ----------
        flux_model_type : str
            Name of the flux model type to use.
            'interp' : an interpolation model.
            'unispline' : a univariate spline interpolation model.
        coil_center : float
            The position (in metres) of the center of the coil of the
            microgenerator, relative to the *top* of the fixed magnet.
        mm : float
            The total height of the magnet assembly (in mm).
        **kwargs
            Keyword argument passed to the `query` method.

        Returns
        -------
        flux model object
            The interpolator object that can be called with `z` values to
            return the flux linkage.

        See Also
        --------
        self.query : underlying method.

        """

        def _get_flux_model(flux_model_str):
            model_dict = {'interp': flux_interpolate,
                          'unispline': flux_univariate_spline}
            return fetch_key_from_dictionary(model_dict,
                                             flux_model_str,
                                             'flux model not found.')

        model_cls = _get_flux_model(flux_model_type)

        phi = self.query(**kwargs)
        flux_model, dflux_model = model_cls(self.z,
                                            phi,
                                            coil_center,
                                            mm=mm)

        return flux_model, dflux_model

    def query(self, **kwargs):
        """Query the database

        Parameters
        ----------
        **kwargs
            kwargs to use in order to query the database. The key-value pairs
            must correspond to the `key_dict` used when adding the item to the
            database

        Returns
        -------
        value
            The data structure stored under the key-value pairs.

        Example
        -------
        >>> key_dict = {'param_1' : param_1_value, 'param_2': param_2_value)
        >>> value = np.ones(3)
        >>> my_flux_database.add(key_dict, value)
        >>> my_flux_database.query(param_1=param_1_value, param_2=param_2_value)
        array([1, 1, 1])

        """
        db_key = self._make_db_key(**kwargs)
        return self.database[db_key]

    def _create_index(self, key_list):
        """
        Create the key look-up table using a list of keys.

        Parameters
        ----------
        key_list : (str, ) array_like
            Keys to use to build the index.

        """
        if self.lut is None:
            self.lut = {}
            for i, k in enumerate(key_list):
                self.lut[k] = i
        else:
            raise ValueError('Index cannot be created more than once.')

    def itervalues(self):
        """Iterate through the values in the database."""
        for key, value in self.database.items():
            yield key, value
