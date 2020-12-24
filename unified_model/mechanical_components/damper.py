from unified_model.utils.utils import fetch_key_from_dictionary
from unified_model.utils.utils import pretty_str


class ConstantDamper:
    """A constant-damping-coefficient damper.

    The force will be equal to the damping coefficient multiplied by a
    velocity, i.e. F = c * v.

    """

    def __init__(self, damping_coefficient):
        """Constructor

        Parameters
        ----------
        damping_coefficient : float
            The constant-damping-coefficient of the damper.

        """
        self.damping_coefficient = damping_coefficient

    def get_force(self, velocity):
        """Get the force exerted by the damper.

        Parameters
        ----------
        velocity : float
            Velocity of the object attached to the damper. In m/s.

        Returns
        -------
        float
            The force exerted by the damper. In Newtons.

        """
        return self.damping_coefficient * velocity

    def __repr__(self):
        return f'ConstantDamper(damping_coefficient={self.damping_coefficient})'

    def __str__(self):
        """Return string representation of the Damper."""
        return f"""ConstantDamper: {pretty_str(self.__dict__, 1)}"""
