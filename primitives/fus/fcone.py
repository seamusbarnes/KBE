#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Required ParaPy Modules
from parapy.geom import *
from parapy.core import *

# Required Modules
from fframe import *
from directories import *
from user import MyColors
from math import sqrt

__all__ = ["FCone"]


class FCone(GeomBase):

    __initargs__ = ["support_frame", "direction", "slenderness_ratio", "fuselage_length", "tip_point_z"]
    __icon__ = os.path.join(DIRS['ICON_DIR'], 'cone.png')

    # A parameter for debugging, turns the visibility of miscellaneous parts ON/OFF
    __show_primitives = False  # type: bool

    support_frame = Input(FFrame(width=1.0, height=0.5))  #
    tangents = Input(['test'])  # Bottom Vector, Side Vector Top Vector
    side_tangent = Input(Vector(-0.88, -0.65, 0))
    top_tangent = Input(Vector(0.8851351164623547, 0, 0.46533410105554684))
    direction = Input('x_', validator=val.OneOf(["x", "x_"]))
    slenderness_ratio = Input(0.3, validator=val.Positive())  # Nose-cone length / frame diagonal
    transparency = Input(0.5)

    @Attribute
    def length(self):
        diagonal = sqrt((self.support_frame.height ** 2) + (self.support_frame.width ** 2))
        return self.slenderness_ratio * diagonal

    @Attribute
    def build_direction(self):
        value = (-1 if self.direction == 'x_' else 1)
        return value

    @Attribute
    def side_tangent_reflected(self):
        x = self.side_tangent.x
        y = self.side_tangent.y
        z = self.side_tangent.z
        return Vector(x, -y, z)


    @Attribute
    def tip_point(self):
        support_position = self.support_frame.position
        support_mid_point = self.support_frame.spline_points[1]
        # delta_z = self.build_direction * (self.side_tangent.z / self.side_tangent.x) * self.length
        return Point(support_position.x + (self.build_direction * self.length),
                     support_position.y, support_mid_point.z)

    @Attribute
    def guides(self):
        start_frame = self.support_frame
        points = start_frame.spline_points

        frame_curve = self.support_frame.frame
        frame_curve_split = SplitCurve(curve_in=frame_curve, tool=points[1]).edges

        v_curve = InterpolatedCurve(points=[points[0], self.tip_point, points[2]],
                                    tangents=[Vector(self.build_direction, 0, 0),  # Bottom forced Horizontal
                                              Vector(0, 0, 1),  # Mid-Point Vector (Forced z+ from sign convention)
                                              self.top_tangent])
        v_curve_split = SplitCurve(curve_in=v_curve, tool=self.tip_point).edges

        h_curve = InterpolatedCurve(points=[points[1], self.tip_point, points[3]],
                                    tangents=[self.side_tangent,
                                              Vector(0, -1, 0),  # Mid-Point Vector (Forced y-)
                                              self.side_tangent_reflected])
        h_curve_split = SplitCurve(curve_in=h_curve, tool=self.tip_point).edges

        return {'f_curve': frame_curve_split, 'v_curve': v_curve_split, 'h_curve': h_curve_split}

    # --- Output Surface: ---------------------------------------------------------------------------------------------

    @Part
    def cone_right(self):
        return SewnShell([self.filled_top, self.filled_bot])

    # --- Primitives: -------------------------------------------------------------------------------------------------

    @Part(in_tree=__show_primitives)
    def filled_top(self):
        return FilledSurface(curves=[self.guides['f_curve'][1], self.guides['v_curve'][1].reversed,
                                     self.guides['h_curve'][0].reversed])

    @Part(in_tree=__show_primitives)
    def filled_bot(self):
        return FilledSurface(curves=[self.guides['h_curve'][0], self.guides['v_curve'][0].reversed,
                                     self.guides['f_curve'][0]])

if __name__ == '__main__':
    from parapy.gui import display

    obj = FCone()
    display(obj)
