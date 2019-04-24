#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Useful package for checking working directory as well as the files inside this directory

# Required ParaPy Modules
from parapy.core import *

# Importing Necessary Classes
from wingpowerloading import WingPowerLoading
from weightestimator import *
from directories import *
from designinput import valid_payloads
from components import EOIR
from definitions import warn_window

__author__ = ["Şan Kılkış", "Nelson Johnson"]
__all__ = ["ParameterGenerator"]
__settable__ = (True if __name__ == '__main__' else False)


class ParameterGenerator(Base):
    """ This class contains all the global design variables.

    :param performance_goal: The goal for which the UAV should be optimized (i.e. 'endurance or 'range')
    :type performance_goal: str
    """

    __icon__ = os.path.join(DIRS['ICON_DIR'], 'parameters.png')

    performance_goal = Input('endurance', validator=val.OneOf(['endurance', 'range']), settable=__settable__)

    goal_value = Input(1.0, validator=val.Positive(), settable=__settable__)

    weight_target = Input('payload', validator=val.OneOf(['payload', 'mtow']), settable=__settable__)

    target_value = Input(0.25, validator=val.Positive(), settable=__settable__)

    payload_type = Input('eoir', validator=val.OneOf(valid_payloads()), settable=__settable__)  #

    configuration = Input('conventional', validator=val.OneOf(['conventional']),settable=__settable__)

    handlaunch = Input(True, validator=val.IsInstance(bool), settable=__settable__)

    portable = Input(True, validator=val.IsInstance(bool), settable=__settable__)

    @target_value.on_slot_change
    def payload_checker(self):
        """ Adds a listener to the :param:`target_value` in order to alert the user that their desired payload has
        been substituted by a commercially available EOIR sensor, in the future when multiple payload types are
        available this """
        if self.weight_target is 'payload':
            actual_weight = EOIR(target_weight=self.target_value).weight
            warn_window("No payload matching a weight of %1.1f [kg] were found, instead a value"
                         "of %1.1f [kg] will be used from now on" % (self.target_value, actual_weight))
            print actual_weight

    @Part
    def weightestimator(self):
        """ Instantiates the :class:`ClassOne` to perform initial weight estimations utilizing statisctics """
        return ClassOne(weight_target=self.weight_target,
                        target_value=self.target_value if self.weight_target is 'payload' else self.target_value,
                        label='Class-I Weight Estimation')

    @Part
    def wingpowerloading(self):
        """ Instantiates the :class:`WingPowerLoading` to be able to choose a suitable design point WingPowerLoading """
        return WingPowerLoading(weight_mtow=self.weight_mtow,
                                performance_goal=self.performance_goal,
                                range=self.goal_value,
                                endurance=self.goal_value,
                                weight_payload=self.weight_payload,
                                handlaunch=self.handlaunch,
                                label='Design Point Selection')

    @Attribute
    def weight_mtow(self):
        """ Fetches the output maximum take-off weight from the Class I weight estimation

        :return: Maximum Take-Off Weight (MTOW) in SI kilogram [kg]
        :rtype: float
        """
        #  Here we obtain the MTOW of the UAV, from the Class I estimation in SI kilogram [kg]
        return self.weightestimator.weight_mtow

    @Attribute
    def weight_payload(self):
        #  Here we obtain the payload mass of the UAV, from the Class I estimation.
        return self.weightestimator.weight_payload

    @Attribute
    def wing_planform_area(self):
        #  Here we calculate the required wing loading from the mtow and design point.
        return self.weight_mtow/self.wing_loading

    @Attribute
    def aspect_ratio(self):
        #  Here we pull the UAV's aspect ratio from the design point.
        return self.wingpowerloading.designpoint['aspect_ratio']

    @Attribute
    def lift_coef_max(self):
        #  Here we pull the UAV's maximum lift coefficient from the design point.
        return self.wingpowerloading.designpoint['lift_coefficient']

    @Attribute
    def stall_speed(self):
        return self.wingpowerloading.stall_speed

    @Attribute
    def design_speed(self):
        return self.wingpowerloading.cruise_parameters['v_opt']

    @Attribute
    def power_loading(self):
        #  Here we pull the UAV's power loading from the design point.
        return self.wingpowerloading.designpoint['power_loading']

    @Attribute
    def wing_loading(self):
        #  Here we pull the UAV's wing loading from the design point.
        return self.wingpowerloading.designpoint['wing_loading']

    @Attribute
    def motor_power(self):
        return ((9.81 / self.power_loading) * self.weight_mtow) / self.wingpowerloading.eta_prop

    @Attribute
    def rho(self):
        return self.wingpowerloading.rho


if __name__ == '__main__':
    from parapy.gui import display

    obj = ParameterGenerator(label='ParameterGenerator')
    display(obj)
