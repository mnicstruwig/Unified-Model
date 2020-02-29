"""
Contains the unified model architecture that encapsulates the mechanical
system, electrical system, the coupling between them and the master system
model that describes their interaction.
"""
from glob import glob
import os
import cloudpickle
import numpy as np
from scipy import integrate
from unified_model.utils.utils import parse_output_expression
from unified_model.evaluate import MechanicalSystemEvaluator, ElectricalSystemEvaluator
from unified_model.utils.utils import pretty_str


class UnifiedModel(object):
    """Unified model class

    This class is used to solve your combined or unified electrical and
    mechanical models.

    Attributes
    ----------
    mechanical_model : instance of `MechanicalModel`
        The mechanical model to use as part of the unified model.
    electrical_model : instance of `ElectricalModel`
        The electrical model to use as part of the unified model.
    coupling_model : instance of `CouplingModel`
        The electro-mechanical coupling to use as part of the unified model.
    governing_equations: func
        The set of governing equations to solve using the unified model.
    raw_solution : ndarray
        The raw post-pipeline output of the solution of the governing
        equations. Intended for debugging purposes.
        Note that the dimensions of `raw_solution` is reversed: each
        row represents all the values for each differential equation
        expressed in `y` by the governing equations.
    post_processing_pipeline : dict
        Dict where keys are pipeline names and values are functions that
        accepts as a single argument the `self.raw_solution` ndarray and
        returns the processed result.
    time : ndarray
        The time steps of the solution to the governing equations.

    """
    def __init__(self):
        """Constructor."""
        self.mechanical_model = None
        self.electrical_model = None
        self.coupling_model = None
        self.governing_equations = None
        self.raw_solution = None
        self.post_processing_pipeline = {}
        self.time = None

    def __str__(self):
        """Return string representation of the UnifiedModel"""
        return f'Unified Model: {pretty_str(self.__dict__)}'

    def save_to_disk(self, path):
        """Persists a unified model to disk"""

        if not os.path.exists(path):
            os.makedirs(path)
        else:
            raise FileExistsError('The path already exists.')

        for key, val in self.__dict__.items():
            component_path = path + key + '.pkl'
            with open(component_path, 'wb') as f:
                cloudpickle.dump(val, f)

    @classmethod
    def load_from_disk(self, path):
        """Load a unified model from disk."""
        unified_model = UnifiedModel(name=None)

        try:
            assert os.path.isdir(path)
        except AssertionError:
            raise FileNotFoundError('Path to model does not exist')

        files = glob(path + '*')
        keys = [f.split('.pkl')[0].split('/')[-1] for f in files]  # TODO: Use regex instead

        for key, file_ in zip(keys, files):
            with open(file_, 'rb') as f:
                unified_model.__dict__[key] = cloudpickle.load(f)

        return unified_model

    def set_mechanical_model(self, mechanical_model):
        """Add a mechanical model to the unified model

        Parameters
        ----------
        mechanical_model : instance of `MechanicalModel`
            The mechanical model to add to the unified model.
            Is passed to `governing_equations` function when the `solve`
            method is called.

        """
        self.mechanical_model = mechanical_model
        return self

    def set_electrical_model(self, electrical_model):
        """Add an electrical model to the unified model

        Parameters
        ----------
        electrical_model : instance of `ElectricalModel`
            The electrical model to add to the unified model.
            Is passed to `governing_equations` function when the `solve`
            method is called.

        """
        self.electrical_model = electrical_model
        return self

    def set_coupling_model(self, coupling_model):
        """Add the electro-mechanical coupling to the unified model.

        Parameters
        ----------
        coupling_model : instance of `CouplingModel`
            The coupling model to add to the unified model.
            Is passed to `governing_equations` function when the `solve`
            method is called.

        """
        self.coupling_model = coupling_model
        return self

    def set_governing_equations(self, governing_equations):
        """Add a set of governing equations to the unified model.

        The governing equations describe the behaviour of the entire system,
        and control the manner in which the various components interact.

        Must accept arguments `t` and `y` and keyword arguments
        `mechanical_model`, `electrical_model` and `coupling_model`.The
        structure and return value of `governing_equations` must be of the same
        as functions solved by `scipy.integrate.solve_ivp` (but have the
        additional keyword arguments specified above).

        Parameters
        ----------
        governing_equations : func
            Set of governing equations that controls the unified model's
            behaviour.

        See Also
        --------
        scipy.integrate.solve_ivp : function
            `governing_equations` must be compatible with the class of function
            solved by `scipy.integrate.solve_ivp`.

        """
        self.governing_equations = governing_equations
        return self

    def set_post_processing_pipeline(self, pipeline, name):
        """Add a post-processing pipeline to the unified model

        After solving the unified model, optional post-processing pipelines can
        be executed on the resulting solution data. This is useful for clipping
        certain values, resampling or filtering noise.

        The pipelines will be executed in the order that they are added.

        Parameters
        ----------
        pipeline : func
            Function that accepts an ndarray of dimensions (N, d), where
            N is the number of time points for which a solution has been
            computed, and d is the dimension of the solution vector `y`
            that is passed into the governing equations.
        name : str
            Name of the pipeline.

        See Also
        --------
        self.set_governing_equations : function that adds the governing
            equations to the unified model.

        """
        self.post_processing_pipeline[name] = pipeline
        return self

    def _apply_pipeline(self):
        """Execute the post-processing pipelines on the raw solution.."""
        for _, pipeline in self.post_processing_pipeline.items():
            # raw solution has dimensions d, n rather than n, d
            self.raw_solution = np.array([pipeline(y) for y in self.raw_solution.T]).T

    def solve(self, t_start, t_end, y0, t_max_step=1e-5, method='RK45'):
        """Solve the unified model.

        Parameters
        ----------
        t_start : float
            The start time of the simulation.
        t_end : float
            The end time of the simulation
        y0 : ndarray
            The initial values of `y`, or the result vector that is passed
            to the governing equations.
        t_max_step : float, optional
            The maximum time step (in seconds) to be used when solving the
            unified model. Default value is 1e-5.
        method : str
            Numerical method to use when solving the unified model. For a
            selection of valid choices, see the `scipy.integrate.solve_ivp`
            method.

        See Also
        --------
        scipy.integrate.solve_ivp : Function used to solve the governing
            equations of the unified model.

        """
        high_level_models = {
            'mechanical_model': self.mechanical_model,
            'electrical_model': self.electrical_model,
            'coupling_model': self.coupling_model
        }

        psoln = integrate.solve_ivp(fun=lambda t, y: self.governing_equations(t, y, **high_level_models),
                                    t_span=[t_start, t_end],
                                    y0=y0,
                                    max_step=t_max_step)

        self.time = psoln.t
        self.raw_solution = psoln.y
        self._apply_pipeline()

    def get_result(self, **kwargs):
        """Get a dataframe of the results using expressions.

        *Any* reasonable expression is possible. You can refer to each of the
        differential equations that represented by the mechanical system model
        using the letter 'x' with the number appended. For example `x1` refers
        to the first differential equation, `x2` to the second, etc.

        Each expression is available as a column in the returned pandas
        dataframe, with the column name being the key of the kwarg used.

        Parameters
        ----------
        **kwargs
            Each key is the name of the column of the returned dataframe.
            Each value is the expression to be evaluated.

        Returns
        -------
        pandas dataframe
            Output dataframe containing the evaluated expressions.

        See Also
        --------
        unified_model.utils.utils.parse_output_expression : helper function
            that contains the parsing logic.

        Example
        --------
        Here we use previously-built and solved unified model
        >>> unified_model
        <unified_model.unified.UnifiedModel at 0x7fa9e45a83c8>
        >>> print(unified_model.raw_solution)
        [[1 2 3 4 5]
         [1 1 1 1 1]]
        >>> unified_model.get_result(an_expr='x1', another_expr='x2-x1', third_expr='x1*x2')
           an_expr  another_expr  third_expr
        0        1             0           1
        1        2            -1           2
        2        3            -2           3
        3        4            -3           4
        4        5            -4           5

        """
        return parse_output_expression(self.time, self.raw_solution, **kwargs)

    def score_mechanical_model(self,
                               time_target,
                               y_target,
                               metrics_dict,
                               prediction_expr,
                               warp=False,
                               **kwargs):
        """Evaluate the mechanical model using a selection of metrics.

        This is simply a useful helper function that makes use of the various
        evaluation tools that are present to allow for a neat and easier-to-use
        manner of evaluating the mechanical model component of the unified
        model.

        Parameters
        ----------
        metrics_dict: dict
            Metrics to compute on the predicted and target mechanical data.
            Keys must be the name of the metric returned in the Results object.
            Values must be the function used to compute the metric. The
            function must accept to numpy arrays (arr_predict, arr_target) as
            input.
        prediction_expr : str
            Expression that is evaluated and used as the predictions for the
            mechanical system. *Any* reasonable expression is possible. You
            can refer to each of the differential equations referenced by the
            `governing_equations` using the letter `x` with the number appended.
            For example, `x1` refers to the first differential equation, and
            `x2` refers to the second differential equation. Some additional
            functions can also be applied to the differential equations. These
            are referenced in the "See Also" section below.
        y_target : array
            Manually specify the target values. Specifying `y_target` will
            take precedence over the labels processed from
            `labeled_video_processor` and `video_labels_df`.
        time_target : array
            Manually specify the corresponding target time values. Specifying
            `y_target` will  take precedence over the labels processed from
            `labeled_video_processor` and `video_labels_df`.
        warp : bool, optional
            Score using after dynamically time-warping the prediction and
            target signals.
            Default value is False.
        **kwargs
            return_evaluator : bool
                Whether to return the evaluator used to score the electrical
                system.

        See Also
        --------
        unified_model.evaluate.LabeledVideoProcessor : class
            Class used to preprocess `video_labels_df`
        unified_model.evaluate.MechanicalSystemEvaluator.score : method
            Method that implements the scoring mechanism.
        unified_model.unified.UnifiedModel.get_result : method
            Method used to evaluate `prediction_expr`.
        unified_model.utils.utils.parse_output_expression : function
            Function that details additional functions that can be applied
            using `prediction_expr`.

        Example
        -------
        Here we use a previously created unified model
        >>> unified_model.solve(t_start=0,
        ...                     t_end=10,
        ...                     y0=initial_conditions,
        ...                     t_max_step=1e-3)
        >>> mechanical_metrics = {'mde': median_absolute_error,
        ...                       'mape': mean_absolute_percentage_err,
        ...                       'max': max_err}
        >>> pixel_scale = 0.18745
        >>> labeled_video_processor = LabeledVideoProcessor(L=125,
        ...                                                 mm=10,
        ...                                                 seconds_per_frame=3/240,
        ...                                                 pixel_scale=pixel_scale)
        >>> mech_scores = unified_model.score_mechanical_model(metrics_dict=mechanical_metrics,
        ...                                                    video_labels_df=sample.video_labels_df,
        ...                                                    labeled_video_processor=labeled_video_processor,
        ...                                                    prediction_expr='x3-x1')

        """

        # Calculate prediction using expression
        df_result = self.get_result(time='t',
                                    prediction=prediction_expr)
        y_predict = df_result['prediction'].values
        time_predict = df_result['time'].values

        # Scoring
        mechanical_evaluator = MechanicalSystemEvaluator(y_target,
                                                         time_target,
                                                         warp)
        mechanical_evaluator.fit(y_predict, time_predict)
        mechanical_scores = mechanical_evaluator.score(**metrics_dict)

        if kwargs.pop('return_evaluator', None):
            return mechanical_scores, mechanical_evaluator
        return mechanical_scores

    def score_electrical_model(self,
                               time_target,
                               emf_target,
                               metrics_dict,
                               prediction_expr,
                               warp=False,
                               **kwargs):
        """Evaluate the electrical model using a selection of metrics.

        This is simply a useful helper function that makes use of the various
        evaluation tools that are present to allow for a neat and easier-to-use
        manner of evaluating the electrical model component of the unified
        model.

        Parameters
        ----------
        metrics_dict: dict
            Metrics to compute on the predicted and target electrical data.
            Keys will be used to set the attributes of the Score object.
            Values must be the function used to compute the metric. Each function
            must accept arguments (arr_predict, arr_target) as input, where
            `arr_predict` and `arr_target` are numpy arrays that contain the
            predicted values and target values, respectively. The return value
            of the functions can have any shape.
        prediction_expr : str
            Expression that is evaluated and used as the predictions for the
            electrical system. *Any* reasonable expression is possible. You
            can refer to each of the differential equations referenced by the
            `governing_equations` using the letter `x` with the number appended.
            For example, `x1` refers to the first differential equation, and
            `x2` refers to the second differential equation. Some additional
            functions can also be applied to the differential equations. These
            are referenced in the "See Also" section below.
        **kwargs
            closed_circuit : bool
                If True, consider the voltage across the *load*, and not the
                open-circuit voltage across the whole system.
                Default value is False.
            return_evaluator : bool
                Whether to return the evaluator used to score the electrical
                system.
            clip_threshold : float
                If greater than 0., clip the leading and trailing emf target
                samples that don't include signal information by taking a
                spectrogram. Default value is 1e-4.

        Returns
        -------


        See Also
        --------
        unified_model.evaluate.AdcProcessor : class
            Class used to preprocess `adc_df`
        unified_model.evaluate.ElectricalSystemEvaluator.score : method
            Method that implements the scoring mechanism.
        unified_model.unified.UnifiedModel.get_result : method
            Method used to evaluate `prediction_expr`.
        unified_model.utils.utils.parse_output_expression : function
            Function that details additional functions that can be applied
            using `prediction_expr`.

        Example
        -------
        Here we use a previously created unified model
        >>> unified_model.solve(t_start=0,
        ...                     t_end=10,
        ...                     y0=initial_conditions,
        ...                     t_max_step=1e-3)
        >>> electrical_metrics = {'rms': root_mean_square}
        >>> adc_processor = AdcProcessor(voltage_division_ratio=1/0.3)
        >>> electrical_scores = unified_model.score_electrical_model(metrics_dict=electrical_metrics,
        ...                                                          adc_df=sample.adc_df,
        ...                                                          adc_processor=adc_processor,
        ...                                                          prediction_expr='g(t, x5)')

        """
        # calculate prediction using expression
        df_result = self.get_result(time='t',
                                    prediction=prediction_expr)
        emf_predict = df_result['prediction'].values
        time_predict = df_result['time'].values

        if kwargs.pop('closed_circuit', False):
            R_coil = self.electrical_model.coil_resistance
            R_load = self.electrical_model.load_model.R
            emf_predict = emf_predict*(R_load/(R_load+R_coil))  # Load voltage

        # Scoring
        clip_threshold = kwargs.pop('clip_threshold', 1e-4)
        electrical_evaluator = ElectricalSystemEvaluator(emf_target,
                                                         time_target,
                                                         warp,
                                                         clip_threshold)

        electrical_evaluator.fit(emf_predict,
                                 time_predict)

        electrical_scores = electrical_evaluator.score(**metrics_dict)

        if kwargs.pop('return_evaluator', None):
            return electrical_scores, electrical_evaluator
        return electrical_scores
