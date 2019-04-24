#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Importing required local packages
from parapy.core import *
from math import *
import matplotlib.pyplot as plt
from directories import *
from components import EOIR, FlightController
from definitions import error_window


__author__ = ["Nelson Johnson", "Şan Kılkış"]
__all__ = ["WingPowerLoading"]
__settable__ = (True if __name__ == '__main__' else False)


class WingPowerLoading(Base):
    """ This class will construct the wing and power loading plot for the fixed wing UAV based on the input MTOW. The
    requirements are the climb rate and climb gradient. There are assumed values for:  C_lmax, Stall speed,
    propeller efficiency, zero-lift drag coefficient, Aspect Ratio and Oswald Efficiency Factor. All Values are in
    SI Units unless stated.

    :param weight_mtow: The Maximum Take-Off Weight from Class I in SI kilogram [kg]
    :type weight_mtow: float

    :param performance_goal: The UAV performance goal (either 'endurance', or 'range')
    :type performance_goal: str

    :param range: The UAV design range in SI kilometer [km]
    :type range: float

    :param endurance: The UAV design endurance in SI hours [h]
    :type endurance: float

    :param weight_payload: The UAV design payload weight in SI kilogram [kg]
    :type weight_payload: float

    :param handlaunch: Handles the switch case of whether the user whether the UAV is to be handlaunched
    :type handlaunch: bool

    :param maximum_lift_coefficient: A list of three C_lmax's that the wing is assumed to generate which create \
    multiple lines on the thrust/wing loading plots.
    :type maximum_lift_coefficient: list

    :param aspect_ratio_range: A list of two potential aspect ratios for the design
    :type aspect_ratio_range: list

    :param eta_prop: This is the assumed propeller efficiency.
    :type eta_prop: float

    :param eta_motor: This is the assumed motor efficiency.
    :type eta_motor: float

    :param e_factor: This is the assumed oswald efficiency factor.
    :type e_factor: float

    :param rho: This is the STD ISA sea level density
    :type rho: float

    :param rho_cr: This is the ISA Density at 3km height for the climb rate power loading equation.
    :type rho_cr: float

    :param zero_lift_drag: This is the assumed Value of Zero-Lift Drag Coefficient.
    :type zero_lift_drag: float

    :param climb_rate: This is the assumption for Required Climb Rate in m/s, Same as Sparta UAV 1.1.2.
    :type climb_rate: float

    :param climb_gradient: This is the assumed Climb Gradient to clear 10m object 17m away.
    :type climb_gradient: float

    :param stall_speed: This is the assumed stall speed for the UAV.
    :type stall_speed: float
    """

    __icon__ = os.path.join(DIRS['ICON_DIR'], 'designpoint.png')

    #: The Maximum Take-Off Weight from Class I in SI kilogram [kg]
    weight_mtow = Input(5.0, validator=val.Positive(), settable=__settable__)

    #: Performance goal to be optimized for (either 'endurance', or 'range')
    performance_goal = Input('range', validator=val.OneOf(['range', 'endurance']), settable=__settable__)

    #: Design range in SI kilometers [km], depending on the performance_goal this can be ignored
    range = Input(100.0, validator=val.Positive(), settable=__settable__)

    #: Design endurance in SI hours [h], depending on the performance_goal this can be ignored
    endurance = Input(1.0, validator=val.Positive(), settable=__settable__)

    #: Current selected payload weight from Class I in SI kilogram [kg]
    weight_payload = Input(0.2, validator=val.Positive(), settable=__settable__)

    #: Switch case to determine if the user requires the UAV to be hand launched which affects the stall speed
    handlaunch = Input(True, validator=val.IsInstance(bool), settable=__settable__)

    #: STD ISA Sea Level Density in SI kilogram per meter cubed [kg/m^3]
    rho = Input(1.225, validator=val.Positive(), settable=__settable__)

    #: ISA Density at cruise, this value is at 3 [km] height for the climb rate power loading equation
    rho_cr = Input(0.9091, validator=val.Positive(), settable=__settable__)

    #: This is a list of three C_lmax's that the wing is assumed to generate. This creates multiple lines on the plots.
    maximum_lift_coefficient = Input([1.0, 1.25, 1.5], val.IsInstance(list))

    #: This is the assumed propeller efficiency.
    eta_prop = Input(0.7, validator=val.Positive())

    #: This is the assumed motor efficiency.
    eta_motor = Input(0.9, validator=val.Positive())

    #: This is the assumed Oswald Efficiency Factor.
    e_factor = Input(0.8, validator=val.Positive())

    #: Assumed Value of Zero-Lift Drag Coefficient.
    zero_lift_drag = Input(0.02, validator=val.Positive())

    #: Assumption for Required Climb Rate, Same as Sparta UAV 1.1.2.
    climb_rate = Input(1.524, validator=val.Between(1.0, 3.0))

    #: Assumed Climb Gradient to clear 10m object 17m away.
    climb_gradient = Input(0.507, validator=val.Between(0.1, 0.9))

    @Input
    def aspect_ratio_range(self):
        """ Derived input that handles defaulting of the aspect_ratio. These values are determined from reference images
        for drones that are handlaunched vs those that are not.

        :return: Bounds of Acceptable Aspect Ratios
        :rtype: list
        """
        return [10, 12] if self.handlaunch else [12, 20]

    @Input
    def stall_speed(self):
        """ This attribute calculates the stall speed for the UAV depending on whether it will be hand launched or \
        not. If hand launched, the stall speed is to be 8 m/s and if not, it is 12 m/s.

        :rtype: float
        """
        if self.handlaunch is True:
            stall_speed = 8.0
        else:
            stall_speed = 12.0
        return stall_speed

    @aspect_ratio_range.on_slot_change
    def aspect_validator(self):
        """ Validator for the compartment_type """
        if isinstance(self.aspect_ratio_range, list):
                for _ratio in self.aspect_ratio_range:
                    if _ratio < 10:
                        error_window('AR=%d will result in too of an low aspect ratio and thus high induced drag, '
                                     'consider increasing' % _ratio)
                    elif _ratio > 20:
                        error_window('AR=%d will result in too high of anaspect ratio and thus high structural loads '
                                     'due to increased wing bending moments, consider decreasing' % _ratio)
        else:
            raise TypeError('The provided input into :param:`aspect_ratio` is not valid')

    @maximum_lift_coefficient.on_slot_change
    def lift_coef_validator(self):
        """ Validator for the compartment_type """
        if isinstance(self.aspect_ratio_range, list):
                for _coef in self.maximum_lift_coefficient:
                    if _coef < 1 and self.handlaunch:
                        error_window('C_L=%d is too low and will result in either too large of a wing surface, or too'
                                     'high of a launch speed to hand launch. Consider increasing' % _coef)
                    elif _coef > 1.7:
                        error_window('C_L=%d This lift coefficient is very difficult to produce without high lift '
                                     'devices at Low Reynolds numbers decreasing' % _coef)
        else:
            raise TypeError('The provided input into :param:`maximum_lift_coefficient` is not valid')

    @Attribute
    def wingloading(self):
        """ This attribute calculates the 3 required wing loadings from the lift equation, using the stall speed \
        and the three assumed C_lmax's. If the UAV is to be hand launched, a lower stall speed is used. At this moment,\
        this is the only requirement on the wing loading.

        :return: Required wing loading for 3 different C_lmax's
        :rtype: dict
        """
        if self.handlaunch:
            ws_string = '_hand'
        else:
            ws_string = ''
        ws = []
        for i in range(len(self.maximum_lift_coefficient)):
            ws.append(0.5 * self.rho * self.maximum_lift_coefficient[i] * self.stall_speed ** 2)
        return {'values': ws, 'flag': ws_string}

    @Attribute
    def powerloading(self):
        """ Lazy-evaluation of Power Loading due to a Climb Rate Requirement at 3000m for various Aspect Ratios

        :return: Stacked-Array where first dimension corresponds to Aspect Ratio, and sub-dimension contains \
        an array of floats in order of smallest Wing Loading to Largest. This range is set w/ parameter 'WS_range'
        :rtype: dict
        """
        wp_cr = []
        for i in range(len(self.aspect_ratio_range)):
            wp_cr.append([self.eta_prop / (self.climb_rate + sqrt(
                num * (2.0 / self.rho_cr) * (sqrt(self.zero_lift_drag) / (1.81 *
                                                                          ((self.aspect_ratio_range[i] * e) **
                                                                           (3.0 / 2.0))))))
                          for num in self.ws_range])
            # evaluating all values of WS_range w/ list comprehension
        # Picks the first aspect ratio and proceeds since the climb-gradient requirement is not influenced heavily by AR
        wp_cg = []
        for i in range(len(self.maximum_lift_coefficient)):
            wp_cg.append([self.eta_prop / (sqrt(num * (2.0 / self.rho) * (1 / self.climbcoefs['lift'][i])) *
                                           self.climb_gradient + (self.climbcoefs['drag'][0][i] /
                                                                  self.climbcoefs['lift'][i]))
                          for num in self.ws_range])

        return {'climb_rate': wp_cr,
                'climb_gradient': wp_cg}

    @Attribute
    def plot_loadingdiagram(self):
        """ This attribute plots the loading diagram.

         :return: Plot
         """
        fig = plt.figure('LoadingDiagram')
        plt.style.use('ggplot')

        for i in range(len(self.maximum_lift_coefficient)):
            wing_loading = self.wingloading['values'][i]
            plt.plot([wing_loading, wing_loading], [0, 2.0],
                     label='C_Lmax%s = %.2f' % (self.wingloading['flag'], self.maximum_lift_coefficient[i]))

        for i in range(len(self.aspect_ratio_range)):
            plt.plot(self.ws_range,
                     self.powerloading['climb_rate'][i], '--',
                     label='CR, AR = %d' % self.aspect_ratio_range[i])

        for i in range(len(self.maximum_lift_coefficient)):
            plt.plot(self.ws_range,
                     self.powerloading['climb_gradient'][i], '-.',
                     label='CG, C_Lmax = %.2f' % self.maximum_lift_coefficient[i])

        plt.plot(self.designpoint['wing_loading'], self.designpoint['power_loading'],
                 marker='o',
                 markerfacecolor='white',
                 markeredgecolor='black', markeredgewidth=1,
                 linewidth=0,
                 label="Design Point")

        plt.ylabel('W/P [N*W^-1]')
        plt.xlabel('W/S [N*m^-2]')
        plt.axis([min(self.ws_range), max(self.ws_range), 0, 1.0])
        plt.legend()
        plt.title('Wing and Power Loading (Handlaunch = %s)' % self.handlaunch)
        plt.show()
        fig.savefig(fname=os.path.join(DIRS['USER_DIR'], 'plots', '%s.pdf' % fig.get_label()), format='pdf')
        return "Plot generated and closed"

    @Attribute
    def designpoint(self):
        """ An attribute which adds a safety factor to the lift coefficient in order to not stall out \
        during climb-out. Modifying the lift coefficient changes drag coefficients as well due to induced drag, \
        the latter part of this code computes the new drag coefficients.

        :return: Dictionary containing design_point variables ('lift_coefficient') and drag coefficients ('climb_drag')
        :rtype: dict
        """

        #: This value is based on the typical maximum lift that an airfoil generated by a clean airfoil
        lift_coef_realistic = 1.2

        #: Evaluation of the distance between lift_coef_realistic and user-inputed values for C_L
        error = [abs(num - lift_coef_realistic) for num in self.maximum_lift_coefficient]

        #: idx1 is the index corresponding to the minimum value within the array 'error'
        #: in other words idx1 is the index corresponding to the closest user-input value to lift_coef_realistic
        idx1 = error.index(min(error))

        #: ws is the chosen Wing Loading based on idx1
        ws = self.wingloading['values'][idx1]

        #: Evaluation of the distance (error) between the chosen wing-loading and all values in WS_range
        error = [abs(num - ws) for num in self.ws_range]

        #: idx2 is the index corresponding to the closest value in WS_range to the chosen design wing-loading
        idx2 = error.index(min(error))

        optimal_ars = [11, 20]
        if self.handlaunch:
            optimal_ar = optimal_ars[0]
        else:
            optimal_ar = optimal_ars[1]

        #: Evaluation of the distance(error) between user-input aspect ratio and the optimal aspect ratio
        error = [abs(num - optimal_ar) for num in self.aspect_ratio_range]

        #: idx3 corresponds to the index of the closest value within self.AR to the optimal_ar defined by the rule above
        idx3 = error.index(min(error))

        wp_choices = [self.powerloading['climb_rate'][idx3][idx2],
                      self.powerloading['climb_gradient'][idx1][idx2]]
        if self.handlaunch:
            wp = wp_choices[1]
        else:
            wp = wp_choices[1]
        # Went back to utilizing the climb_gradient requirement for non-hand launched UAV's
        # as well since climb_rate is not as critical and produced unrealistic motor selection

        return{'lift_coefficient': self.maximum_lift_coefficient[idx1],
               'aspect_ratio': self.aspect_ratio_range[idx3],
               'wing_loading': ws,
               'power_loading': wp}

    @Attribute
    def climbcoefs(self):
        """ An attribute which adds a safety factor to the lift coefficient in order to not stall out
        during climb-out. Modifying the lift coefficient changes drag coefficients as well due to induced drag
        the latter part of this code computes the new drag coefficients.

        :return: Dictionary containing modified lift coefficients ('climb_lift') and drag coefficients ('climb_drag')
        """
        lift_coef_cg = [num - 0.2 for num in self.maximum_lift_coefficient]
        # Above we subtract 0.2 from climb gradient C_l to keep away from stall during climb out
        drag_coef_cg = []
        for i in range(len(self.aspect_ratio_range)):
            drag_coef_cg.append([(self.zero_lift_drag + num ** 2 / (pi * self.aspect_ratio_range[i] * self.e_factor))
                                 for num in self.maximum_lift_coefficient])

            # Due to how drag_coef_cg is defined, the first array dim is aspect ratios, the second dim is
            # lift coefficient. Thus accessing the 2nd aspect ratio and 1st lift coefficient would be C_dcg[1][0].
        return {'lift': lift_coef_cg,
                'drag': drag_coef_cg}

    @Attribute(private=True)
    def ws_range(self):
        """ This is a dummy list of wing loadings for iterating in the Power Loading Equations.

        :return: List of wing loadings
        :rtype: List
        """
        ws_limit = max(self.wingloading['values'])
        values = [float(i) for i in range(1, int(ceil(ws_limit / 100.0)) * 100)]
        return values

    @Attribute
    def eta_tot(self):
        """ This attribute estimates the propulsive efficiency. This is done by multiplying the propeller and the \
        motor efficiencies

        :return: Propulsive Efficiency
        :rtype: float
        """
        return self.eta_prop*self.eta_motor

    @Attribute
    def cruise_parameters(self):
        """ This attribute calculates the cruise parameters related to the requirement on range [km], or \
        endurance [h]. These relations are from the year 1 Intro to aeronautics flight mechanics module.

        :return: Required battery capacity due to plane drag.
        :rtype: dict
        """
        if self.performance_goal is 'range':
            cl_opt = sqrt(self.zero_lift_drag * pi * self.designpoint['aspect_ratio'] * self.e_factor)
            cd_opt = self.zero_lift_drag + (cl_opt ** 2 / (pi * self.designpoint['aspect_ratio'] * self.e_factor))
            v_opt = sqrt(self.designpoint['wing_loading']*(2/self.rho)*(1/cl_opt))
            v_safe = 5.0 + self.stall_speed  # Safety factor to ensure optimal speed is not too close to stall
            s = self.weight_mtow * 9.81 / self.designpoint['wing_loading']
            d_opt = cd_opt * 0.5 * self.rho * (v_opt ** 2) * s
            t = (self.range * 1000 / v_opt)
            p_req_drag = (d_opt * v_opt) / self.eta_tot
            capacity = p_req_drag * t
            out = {'cl_opt': cl_opt,
                   'cd_opt': cd_opt,
                   'd_opt': d_opt,
                   'v_opt':  v_opt if v_opt > v_safe else v_safe,
                   't': t,
                   'p_req_drag': p_req_drag,
                   'capacity': capacity}

        else:
            cl_opt = sqrt(3 * self.zero_lift_drag * pi * self.designpoint['aspect_ratio'] * self.e_factor)
            cd_opt = self.zero_lift_drag + (cl_opt ** 2 / (pi * self.designpoint['aspect_ratio'] * self.e_factor))
            v_opt = sqrt(self.designpoint['wing_loading'] * (2 / self.rho) * (1 / cl_opt))
            v_safe = 5.0 + self.stall_speed  # Safety factor to ensure optimal speed is not too close to stall
            s = (self.weight_mtow * 9.81) / self.designpoint['wing_loading']
            d_opt = cd_opt * 0.5 * self.rho * (v_opt ** 2) * s
            t = self.endurance * 3600
            p_req_drag = (d_opt * v_opt) / self.eta_tot
            capacity = p_req_drag * t
            out = {'cl_opt': cl_opt,
                   'cd_opt': cd_opt,
                   'd_opt': d_opt,
                   'v_opt': v_opt if v_opt > v_safe else v_safe,
                   't': t,
                   'p_req_drag': p_req_drag,
                   'capacity': capacity}
        return out

    @Attribute
    def payload_power(self):
        """ This attribute gets the required power of the EOIR payload w/ Lazy Evaluation, using the payload weight.

        :return: Required battery power due to payload SI Watt
        :rtype: float
        """
        return EOIR(target_weight=self.weight_payload).specs['power']

    @Attribute
    def flight_controller_power(self):
        """ This attribute gets the required power of the flight computer.

        :return: Required flight computer power.
        :rtype: float
        """
        return FlightController().flight_controller_power

    @Attribute
    def battery_capacity(self):
        """ This attribute calculates the required battery capacity, based on the payload mass, flight computer, and \
         flight performance characteristics. Battery efficiency is assumed to be 100 percent.

         :return: Required Battery Capacity in SI Watt hour
         :rtype: float
         """
        t = self.cruise_parameters['t'] / 3600.0
        flight_power_draw = self.cruise_parameters['p_req_drag'] / self.eta_prop
        capacity = (self.payload_power + flight_power_draw + self.flight_controller_power) * t
        return capacity


if __name__ == '__main__':
    from parapy.gui import display

    obj = WingPowerLoading()
    display(obj)
