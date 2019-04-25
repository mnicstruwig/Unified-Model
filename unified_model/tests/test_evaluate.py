import unittest
from unittest.mock import patch

import numpy as np
from numpy.testing import assert_array_equal
import pandas as pd

from unified_model.evaluate import AdcProcessor, ElectricalSystemEvaluator
from scipy.interpolate import UnivariateSpline


class TestAdcProcessor(unittest.TestCase):
    """Test the `AdcProcessor` class."""

    def test_fit_transform_smooth(self):
        """Test the fit_transform method when the signal must be smoothed"""
        test_adc_processor = AdcProcessor(voltage_division_ratio=1,
                                          smooth=True)

        test_time = np.array([1., 2., 3., 4., 5.])
        test_signal = np.array([1., 2., 3., 2., 1.])
        test_groundtruth_df = pd.DataFrame({'time': test_time,
                                            'test_voltage': test_signal})

        test_smooth_signal = np.array([1, 2., 2., 2., 1.])

        expected_voltage_readings = test_smooth_signal - np.mean(test_smooth_signal)
        expected_time_values = test_time / 1000

        with patch('unified_model.evaluate.smooth_butterworth', return_value=test_smooth_signal) as _:
            actual_voltage_readings, actual_time_values = test_adc_processor.fit_transform(groundtruth_dataframe=test_groundtruth_df,
                                                                                           voltage_col='test_voltage',
                                                                                           time_col='time')

            assert_array_equal(expected_voltage_readings, actual_voltage_readings)
            assert_array_equal(expected_time_values, actual_time_values)

    def test_fit_transform_smooth_kwargs(self):
        """Test the fit_transform method with smoothing kwargs supplied."""
        test_critical_frequency = 1/6
        test_adc_processor = AdcProcessor(voltage_division_ratio=1,
                                          smooth=True,
                                          critical_frequency=test_critical_frequency)

        test_time = np.array([1., 2., 3., 4., 5.])
        test_signal = np.array([1., 2., 3., 2., 1.])
        test_groundtruth_df = pd.DataFrame({'time': test_time,
                                            'test_voltage': test_signal})

        test_smooth_signal = np.array([1, 2., 2., 2., 1.])

        expected_voltage_readings = test_smooth_signal - np.mean(test_smooth_signal)
        expected_time_values = test_time / 1000

        with patch('unified_model.evaluate.smooth_butterworth', return_value=test_smooth_signal) as mock_smooth_butterworth:
            actual_voltage_readings, actual_time_values = test_adc_processor.fit_transform(groundtruth_dataframe=test_groundtruth_df,
                                                                                           voltage_col='test_voltage',
                                                                                           time_col='time')
            assert_array_equal(mock_smooth_butterworth.call_args[0][0], test_signal)
            self.assertEqual(mock_smooth_butterworth.call_args[0][1], test_critical_frequency)
            assert_array_equal(expected_voltage_readings, actual_voltage_readings)
            assert_array_equal(expected_time_values, actual_time_values)

    def test_fit_transform_no_smooth(self):
        """Test the fit_transform method when signal must not be smoothed."""
        test_voltage_division_ratio = 2
        test_adc_processor = AdcProcessor(voltage_division_ratio=test_voltage_division_ratio,
                                          smooth=False)

        test_time = np.array([1., 2., 3., 4., 5.])
        test_signal = np.array([1., 2., 3., 2., 1.])
        test_groundtruth_df = pd.DataFrame({'time': test_time,
                                            'test_voltage': test_signal})

        expected_voltage_readings = test_signal * test_voltage_division_ratio
        expected_voltage_readings = expected_voltage_readings - np.mean(expected_voltage_readings)
        expected_time_values = test_time / 1000

        actual_voltage_readings, actual_time_values = test_adc_processor.fit_transform(groundtruth_dataframe=test_groundtruth_df,
                                                                                       voltage_col='test_voltage',
                                                                                       time_col='time')

        assert_array_equal(expected_voltage_readings, actual_voltage_readings)
        assert_array_equal(expected_time_values, actual_time_values)


class TestElectricalSystemEvaluator(unittest.TestCase):
    """Test the ElectricalSystemEvaluator class."""

    def test_fit(self):
        """Test the fit method."""
        test_emf_target = np.array([1, 2, 3, 4, 5, 4, 3, 2, 1])
        test_time_target = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9])
        test_emf_predict = np.array([1, 2, 3, 4, 5, 6, 5, 4, 3])
        test_time_predict = test_time_target

        test_electrical_system_evaluator = ElectricalSystemEvaluator(emf_target=test_emf_target,
                                                                     time_target=test_time_target)

        # Before fit
        self.assertTrue(test_electrical_system_evaluator.emf_target_ is None)
        self.assertTrue(test_electrical_system_evaluator.emf_predict_ is None)
        self.assertTrue(test_electrical_system_evaluator.time_ is None)

        test_electrical_system_evaluator.fit(emf_predict=test_emf_predict,
                                             time_predict=test_time_target)

        assert_array_equal(test_emf_predict, test_electrical_system_evaluator.emf_predict)
        assert_array_equal(test_time_predict, test_electrical_system_evaluator.time_predict)

        self.assertTrue(isinstance(test_electrical_system_evaluator.emf_target_, np.ndarray))
        self.assertTrue(len(test_electrical_system_evaluator.emf_target_) > 1)
        self.assertTrue(isinstance(test_electrical_system_evaluator.emf_predict_, np.ndarray))
        self.assertTrue(len(test_electrical_system_evaluator.emf_predict_) > 1)
        self.assertTrue(isinstance(test_electrical_system_evaluator.time_, np.ndarray))
        self.assertTrue(len(test_electrical_system_evaluator.time_) > 1)

    def test_fit_transform(self):
        """Test the fit_transform method."""
        test_emf_target = np.array([1, 2, 3, 4, 5, 4, 3, 2, 1])
        test_time_target = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9])
        test_emf_predict = np.array([1, 2, 3, 4, 5, 6, 5, 4, 3])
        test_time_predict = test_time_target

        expected_emf_predict = np.array([1, 2, 3, 4, 5, 6, 5, 4, 3])
        expected_time = test_time_target

        test_electrical_system_evaluator = ElectricalSystemEvaluator(emf_target=test_emf_target,
                                                                     time_target=test_time_target)

        # We test the fit method separately. So let's mock it out
        # here for testing purposes.
        def mock_fit(self, *args, **kwargs):
            self.time_ = expected_time
            self.emf_predict_ = expected_emf_predict

        with patch('unified_model.evaluate.ElectricalSystemEvaluator._fit', new=mock_fit):
            actual_time, actual_emf_predict = test_electrical_system_evaluator.fit_transform(emf_predict=test_emf_predict,
                                                                                             time_predict=test_time_predict)
            assert_array_equal(expected_time, actual_time)
            assert_array_equal(expected_emf_predict, actual_emf_predict)

    def test_score(self):
        """Test the score method."""
        test_emf_target = np.array([1, 2, 3, 4, 5, 4, 3, 2, 1])
        test_time_target = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9])
        test_emf_predict = np.array([1, 2, 3, 4, 5, 6, 5, 4, 3])
        test_time_predict = test_time_target

        test_electrical_system_evaluator = ElectricalSystemEvaluator(emf_target=test_emf_target,
                                                                     time_target=test_time_target)
        test_time_ = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9])
        test_emf_predict_ = np.array([1, 2, 3, 4, 5, 6, 5, 4, 3])

        # We test the fit method separately. So let's mock it out
        # here for testing purposes.
        def mock_fit(self, emf_predict, time_predict):
            self.emf_predict_ = emf_predict  # Fake resampled predicted values
            self.time_ = time_predict  # Fake resampled timestamps
            self.emf_target_ = self.emf_target  # Fake resampled target values

        with patch('unified_model.evaluate.ElectricalSystemEvaluator.fit', new=mock_fit):
            # Mock `fit` method
            test_electrical_system_evaluator.fit(emf_predict=test_emf_predict,
                                                 time_predict=test_time_target)

            def test_metric_mean(x, y):
                return np.mean([x, y])

            def test_metric_max(x, y):
                return np.max([x, y])

            expected_mean = test_metric_mean(test_electrical_system_evaluator.emf_predict_,
                                             test_electrical_system_evaluator.emf_target_)

            expected_max = test_metric_max(test_electrical_system_evaluator.emf_predict_,
                                           test_electrical_system_evaluator.emf_target_)

            actual_result = test_electrical_system_evaluator.score(mean=test_metric_mean,
                                                                   max_value=test_metric_max)

            self.assertEqual(expected_mean, actual_result.mean)
            self.assertEqual(expected_max, actual_result.max_value)