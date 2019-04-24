#!/usr/bin/env python
# -*- coding: utf-8 -*-

from parapy.geom import *  # \
from parapy.core import *  # / Required ParaPy Modules

from user import *
from components.fuselage.primitives import *
from definitions import *
from directories import *
from copy import copy

__author__ = "Şan Kılkış"
__all__ = ["Fuselage"]

# TODO (TBD) Make the boundary condition spline more robust with sorting and lambda functions
# TODO (TBD) Add a validator function for the fuselage promting user input if intersections occur


class Fuselage(ExternalBody):
    """ This class will create a fuselage from frames created from desired internal components.

    :returns: ParaPy Geometry of the Fuselage

    :param compartment_type: Type of containers at each station, possible entries (nose, container, motor, tail)
    :type compartment_type: str list

    """

    __initargs__ = ["compartment_type", "sizing_parts"]
    __icon__ = os.path.join(DIRS['ICON_DIR'], 'fuselage.png')

    __framecache__ = None

    #: Type of containers at each station, possible entries (nose, container, motor, tail)
    #: :type: str list
    compartment_type = Input(['', ''], validator=val.IsInstance(list))

    #: Parts that the fuselage will be sized for, these must correspond to the entries given in `compartment_type`
    #: :type: list
    # sizing_parts = Input()
    sizing_parts = Input([None, None], validator=val.IsInstance(list))

    #: Disables Automatic Fuselage Frame (FFrame) Creation and allows instead manual user-input to set the shape
    #: :type: bool
    auto_fuselage_disable = Input(False, validator=val.IsInstance(bool))

    #: Sets the Padding Factor between Fuselage Sizing Parts
    #: :type: bool
    pad_factor = Input(0.1, validator=val.Between(0.05, 1))

    #: Initiates the automatic frame minimization WARNING: May lead to intersecting surfaces
    #: :type: bool
    minimize_frames = Input(False, validator=val.IsInstance(bool))

    #: Linearly joins the frames of the center fuselage WARNING: May lead to errors at the tail cone
    #: :type: bool
    ruled = Input(False, validator=val.IsInstance(bool))

    #: Toggles transparency of the fuselage
    #: :type: bool
    make_transparent = Input(False, validator=val.IsInstance(bool))

    #: Sets the color of the fuselage (Overwritten from the default yellow)
    #: :type: str or Tuple
    color = Input(MyColors.light_grey)

    #: Changes the number of ply's of carbon fiber http://www.ijera.com/papers/Vol4_issue5/Version%202/J45025355.pdf
    #: :type: tuple
    ply_number = Input(3, validator=val.IsInstance(int))

    @compartment_type.on_slot_change
    def compartment_validator(self):
        """ Validator for the compartment_type """
        if isinstance(self.compartment_type, list):
            for _part in self.compartment_type:
                if _part not in ['nose', 'container', 'motor', 'tail']:
                    raise TypeError('%s is not a valid component type, please restrict input to "nose", "container", '
                                    '"motor" or "tail"' % _part)
                elif not isinstance(_part, basestring):
                    raise TypeError
        else:
            raise TypeError('The provided input into :param:`sizing_parts` is not valid')

    @sizing_parts.on_slot_change
    def sizing_part_validator(self):
        """ Validator for the sizing_parts """
        if isinstance(self.sizing_parts, list):
            for _part in self.sizing_parts:
                if not isinstance(_part, Component):
                    raise TypeError('%s is not a valid component, please check :class:`Component` syntax'
                                    % _part.__repr__)
        else:
            raise TypeError('The provided input into :param:`sizing_parts` is not valid')

    @auto_fuselage_disable.on_slot_change
    def auto_disabler(self):
        """ Pauses dependency tracking and automatic frame generation utilizing a simple caching mechanism. This is done
        in order for the user to be able to make changes to the automatically generated fuselage frames without these
        changes being overwritten by ParaPy due to the fuselage's dependence on the `internal_shapes` input. """
        if self.auto_fuselage_disable:
            # Utilizing a shallow-copy of the frames increases performance since dependency on sizing_parts is removed
            setattr(self, '__framecache__', copy(self.frames))
        else:
            setattr(self, '__framecache__', None)

    @Attribute
    def component_type(self):
        return 'fuselage'

    @Attribute(private=True)
    def frame_builder(self):
        """ This attribute codifies the knowledge for the fuselage and automatically generates the required frames by
        extracting the dimensions of the supplied `sizing_parts' through the methods `bbox_extractor` and `bbox_2_frame`
        This has proven to be a very robust method since it does not depend on the complexity of the input part. Since
        these drones operate at very low mach numbers, the area rule which is commonly used for transonic aircraft
        is not valid. Instead these small drones can benefit from a lifting fuselage which is accomplished through
        having an airfoil like shape (thus a single location of maximum thickness). This location is
        referred to as the fuselage apex and is obtained by comparing the current frame to its sequential neighbor
        which links to a switch case, `apex_reached` and `build_loc`. A forward-chaining inference procedure is used
        in a for loop that traverses the fuselage from nose to tail and fires all fire-able rules sequentially.
        This procedure is preferred since multiple possibilities at each frame location exist (nose, container, motor,
        or tail) along with the same number of possibilities existing at the nearest neighbor. Finally, the start
        and end boundary conditions reject the creation of a nose or tail-cone before the fuselage is built, since both
        of these classes require tangency conditions at the start and end of the fuselage. Thus, the requested class
        is appended to a string array of `still_to_build` which is referenced later in the code.

        :return: A collection of frame variables that are used later in the fuselage class
        :rtype: dict
        """

        if len(self.compartment_type) == len(self.sizing_parts):  # Checking supplied inputs for concurrent dimensions

            frames = []
            still_to_build = []  # Special parts which require the fuselage to be completed before instantiation
            first_container = True  # Boolean to determine if current instance is first occurrence of a container frame
            apex_reached = False  # Boolean that indicates if a maxima in  fuselage thickness has been reached
            apex_index = 0
            build_loc = 'start'  # Switch case to determine frame placement
            for i in range(0, len(self.compartment_type) - 1):
                _type = self.compartment_type[i]
                _next_type = self.compartment_type[i+1]

                # Start Boundary Condition
                if i == 0:
                    if _type == 'nose':
                        still_to_build.append(['nose', i])
                    elif _type == 'boom':
                        raise Exception('A boom has been requested with no supports. Please try again with a boom'
                                        ' instance surrounded by at least 2 frame containers')
                    elif _type == 'motor':
                        frames.append([MFrame(motor_diameter=self.sizing_parts[i].diameter,
                                              position=self.sizing_parts[i].position)])

                # Container Logic
                if _type == 'container':
                    _bbox = self.bbox_extractor(self.sizing_parts[i])  # Fetching current bbox
                    if first_container:  # If current container is the first container a frame is returned
                        frames.append(self.bbox_to_frame(_bbox, build_loc))
                        first_container = False
                    else:
                        if _next_type == 'container':
                            _frame = self.bbox_to_frame(_bbox, build_loc)
                            _next_bbox = self.bbox_extractor(self.sizing_parts[i+1])
                            _next_frame = self.bbox_to_frame(_next_bbox, build_loc)

                            # True would mean that the next frame is larger than the current
                            _width_check = (True
                                            if _frame[1]['width'] < _next_frame[1]['width']
                                            else False)
                            _height_check = (True
                                             if _frame[1]['height'] < _next_frame[1]['height']
                                             else False)

                            if _width_check and _height_check is True:
                                frames.append(self.bbox_to_frame(_bbox, build_loc))
                            elif _width_check is False and _height_check is True:
                                _height_increase = (_next_frame[1]['height'] - _frame[1]['height']) / 2.0
                                _new_box = Box(width=_frame[1]['length'],
                                               length=_frame[1]['width'],
                                               height=_next_frame[1]['height'] + _height_increase,
                                               position=translate(_frame[1]['position'],
                                                                  'x', _frame[1]['length'] / 2.0,
                                                                  'z', _frame[1]['height'] / 2.0),
                                               centered=True)
                                # frames.append(self.bbox_to_frame(_bbox, 'start'))
                                frames.append(self.bbox_to_frame(_new_box.bbox, 'mid'))
                            elif _width_check is True and _height_check is False:
                                _width_increase = (_next_frame[1]['width'] - _frame[1]['width']) / 2.0
                                _new_box = Box(width=_frame[1]['length'],
                                               length=_frame[1]['width'] + _width_increase,  # Uses next width
                                               height=_frame[1]['height'],  # But keeps current height
                                               position=translate(_frame[1]['position'],
                                                                  'x', _frame[1]['length'] / 2.0,
                                                                  'z', _frame[1]['height'] / 2.0),
                                               centered=True)
                                # frames.append(self.bbox_to_frame(_bbox, 'start'))
                                frames.append(self.bbox_to_frame(_new_box.bbox, 'mid'))
                            else:
                                if not apex_reached:  # Creates a frame in-front and behind the largest bbox (apex)
                                    frames.append(self.bbox_to_frame(_bbox, build_loc))
                                    build_loc = 'end'
                                    frames.append(self.bbox_to_frame(_bbox, build_loc))
                                    apex_reached = True
                                    apex_index = i - 1  # Making up for i = 1 being the first frame
                                elif apex_reached:
                                    raise TypeError('Only a fuselage with one apex (location of maximum area) is '
                                                    'allowed. Please re-arrange internals so that maximum thickness'
                                                    ' occurs only once')
                        elif _next_type != 'container':
                            if apex_reached:
                                frames.append(self.bbox_to_frame(_bbox, build_loc))
                            else:
                                frames.append(self.bbox_to_frame(_bbox, 'start'))
                                frames.append(self.bbox_to_frame(_bbox, 'end'))
                                apex_index = i - 1

                # Boom Logic
                # TODO (TBD) Currently not implemented, but would be nice to have in the future for RQ-11 type designs
                elif _type == 'boom':
                    still_to_build.append(['boom', i])

                # End Boundary Condition
                if i + 2 == len(self.compartment_type):
                    if _next_type == 'motor':
                        frames.append([MFrame(motor_diameter=self.sizing_parts[i+1].diameter,
                                              position=self.sizing_parts[i+1].position)])
                    elif _next_type == 'tail':
                        still_to_build.append(['tail', i])

            fuselage_complete = (True if len(still_to_build) is 0 else False)
        else:
            raise IndexError('The supplied inputs do not have the same dimension')

        return {'built_frames': frames,  # type: list
                'apex_index': apex_index,  # type: int
                'still_to_build': still_to_build,  # type: list
                'fuselage_complete': fuselage_complete}  # type: bool

    @Attribute
    def frames(self):
        """ Collection of all center-fuselage section frames (those that were built by `frame_builder`. Each frame has
        an :attr: `frame` and :attr: `points`. If the user option `minimize_frames` is True then only the following
        frames are kept: [start, apex_start, apex_end, end].

        :return: List of center-fuselage section frames
        :rtype: list
        """
        grabbed_frames = [i[0] for i in self.frame_builder['built_frames']]
        apex_index = self.frame_builder['apex_index']

        # Frame-minimization algorithm, USE WITH CAUTION!
        if self.minimize_frames:
            index_to_keep = [0, apex_index, apex_index+1, len(grabbed_frames) - 1]
            grabbed_frames = [grabbed_frames[i] for i in range(0, len(grabbed_frames))
                              if i in index_to_keep]

        # Grabbing-cached frames if they exist
        if self.__framecache__ is not None:
            grabbed_frames = self.__framecache__
        return grabbed_frames

    @Attribute
    def curves(self):
        """ Grabs all curves out of the list `frames`

        :return: List of curves
        :rtype: list
        """
        return [i.curve for i in self.frames]

    @Attribute
    def points(self):
        """ Grabs all spline_points out of the list `frames`. Due to how the primitive class `Frame` is defined
        the significance of the points in order is as follows: Point 0 = Bottom (start), Point 1 = Right Side,
        Point 2 = Top (end), Point 3 = Left Side

        :return: List of spline_points in
        """
        return [i.spline_points for i in self.frames]

    @Attribute
    def side_bc(self):
        """ The side tangency boundary condition required for the fuselage nose and tail. This is obtained by fitting
        a curve through all side-points (Point 1 of Attribute `points`). Since, the fuselage shell is lofted from nose
        to tail (toward positive `x`) the start tangent and end tangents, obtained from a `FittedCurve`
        both face this direction. Thus, to create a nose cone, which has a build direction of `x_` the direction of the
        start_tangent must be reversed. BC 0 = Start Tangent (Direction `x_`), BC 1 = End Tangent (Direction `x`).

        :returns: List containing the start and end tangent vectors, and construction spline, included for debugging
        :rtype: Vector


        """
        # Point 0 = Bottom, Point 1 = Side, Point 2 = Top, Point 3 = Side Reflected
        points = [i[1] for i in self.points]
        spline = FittedCurve(points)  # Fitted Curve best reproduces the algorithm present in LoftedShell

        start_tangent = spline.tangent1.reverse  # Opposite direction required due to sign convention in FFrame
        end_tangent = spline.tangent2

        return start_tangent, end_tangent, spline

    @Attribute
    def top_bc(self):
        """ The top tangency boundary condition required for the fuselage nose and tail. This is obtained by extracting
        the start and end tangents of the inner top edge from the attribute `center_section_left`. Keeping in-line with
        the definition of points in the frame primitives, the interpolated curve is conveniently constructed from the
        bottom point (Point 0) to the top point (Point 2). However, due to this convention the direction of the end
        tangent must be reversed.

        :returns: List containing the start and end tangent vectors
        :rtype: Vector
        """
        # Due to the build order edge 1 will always be the top curve
        spline = self.center_section_left.edges[1]

        start_tangent = spline.tangent1

        end_tangent = spline.tangent2  # Not true when ruled mode is turned
        x = end_tangent.x
        y = 0  # Forced to zero to avoid minute floating point errors
        z = end_tangent.z
        end_tangent = Vector(-x, y, -z)  # Opposite direction required due to the build convention in Frame

        return start_tangent, end_tangent

    @Attribute
    def center_of_gravity(self):
        """ Area weighted average of center of gravity

        :return: Position of the center of gravity in 3D space (x, y, z) w.r.t the origin XOY in [SI Meter]
        :rtype: Point
        """
        # Array Index 0 = Area, Array Index 1 = cog
        nose = ([self.nose.cone.area, self.nose.cone.cog]
                if self.build_nose
                else [0, Point(0, 0, 0)])
        tail = ([self.tail.cone.area, self.tail.cone.cog]
                if self.build_tail
                else [0, Point(0, 0, 0)])
        center = [self.center_section.area, self.center_section.cog]

        total_area = nose[0] + tail[0] + center[0]

        x_loc = (nose[0] * nose[1].x) + (tail[0] * tail[1].x) + (center[0] * center[1].x) / total_area
        y_loc = (nose[0] * nose[1].y) + (tail[0] * tail[1].y) + (center[0] * center[1].y) / total_area
        z_loc = (nose[0] * nose[1].z) + (tail[0] * tail[1].z) + (center[0] * center[1].z) / total_area

        return Point(x_loc, y_loc, z_loc)

    # --- Output Shapes: ----------------------------------------------------------------------------------------------

    @Attribute(in_tree=True)
    def center_section(self):
        """ The main output shape of the class Fuselage, constructed from the Private Attributes below """
        return SewnShell([self.center_section_left, self.center_section_right],
                         color=self.color,
                         transparency=self.transparency)

    @Attribute(in_tree=True)
    def nose(self):
        """ Returns the nose cone of the fuselage is asked, otherwise returns a hidden circle. NOTE: This workaround
        was necessary to produce the parts in the tree, while still preserving lazy evaluation """
        if self.build_nose:
            shape_out = FCone(support_frame=self.frames[0],
                              top_tangent=self.top_bc[0], side_tangent=self.side_bc[0], direction='x_',
                              color=self.color,
                              transparency=self.transparency)
        else:
            shape_out = Circle(radius=0, hidden=True)
        return shape_out

    @Attribute(in_tree=True)
    def tail(self):
        """ Returns the tail cone of the fuselage is asked, otherwise returns a hidden circle. NOTE: This workaround
         was necessary to produce the parts in the tree, while still preserving lazy evaluation """
        if self.build_tail:
            shape_out = FCone(support_frame=self.frames[-1],
                              top_tangent=self.top_bc[1], side_tangent=self.side_bc[1], direction='x',
                              color=self.color,
                              transparency=self.transparency)
        else:
            shape_out = Circle(radius=0.0, hidden=True)
        return shape_out

    @Attribute(private=True)
    def internal_shape(self):
        """ This overwrites the Part defined in the class `Component` an internal_shape w/ a Dummy Value"""
        return None

    @Attribute(private=True)
    def fuselage_joiner(self):
        """ Joines the current instantiated elements (nose/tail cone(s)) of the fuselage and outputs a single part"""
        if self.build_tail and self.build_nose:
            first_iter = Fused(self.center_section, self.tail.cone)
            shape_out = Fused(first_iter, self.nose.cone, hidden=True)
        elif self.build_tail:
            shape_out = Fused(self.center_section, self.tail.cone, hidden=True)

        elif self.build_nose:
            shape_out = Fused(self.center_section, self.nose.cone, hidden=True)
        else:
            raise Exception('%s Fuselage construction failed' % self)
        return shape_out

    @Part
    def external_shape(self):
        return ScaledShape(shape_in=self.fuselage_joiner, reference_point=Point(0, 0, 0), factor=1, label=self.label)

    # --- Private Attributes: -----------------------------------------------------------------------------------------

    @Attribute(private=True)
    def transparency(self):
        """ Switch case that returns the proper transparency value based on the status of `show_internals`

        :return: Transparency value
        """
        return 0.5 if self.make_transparent else None

    @Attribute(private=True)
    def center_section_left(self):
        """ The main fuselage section excluding nose and tail """
        return LoftedShell(profiles=self.curves, check_compatibility=True, ruled=self.ruled)

    @Attribute(private=True)
    def center_section_right(self):
        """ The mirror image of `center_section_left` since by definition half-frames are used """
        return MirroredShape(shape_in=self.center_section_left,
                             reference_point=self.position,
                             vector1=self.position.Vx_,
                             vector2=self.position.Vz)

    @Attribute(private=True)
    def build_nose(self):
        """ Switch case that that returns True/False if a nose is specified in `compartment_type`

        :rtype: bool
        """
        return any('nose' in i for i in self.frame_builder['still_to_build'])

    @Attribute(private=True)
    def build_tail(self):
        """ Switch case that that returns True/False if a tail is specified in `compartment_type`

        :rtype: bool
        """
        return any('tail' in i for i in self.frame_builder['still_to_build'])

    # --- Methods: ----------------------------------------------------------------------------------------------------

    @staticmethod
    def bbox_to_frame(bbox, placement='start'):
        """ Responsible for instantiating the frame that is fit around a certain Bounding-box (bbox)

        :param bbox: The input bbox for the frame to be fit around
        :param placement: Determines if the frame will be placed at the start (min(x)) middle or end (max(x))
        :return: Fuselage Frame
        :rtype: FFrame
        """

        # Extracting corners from bbox
        corners = bbox.corners
        point0 = min(corners)
        point1 = max(corners)

        # Determining width, height, and length of each frame (More robust than calling ordered faces)
        width = abs(point1.y-point0.y)
        height = abs(point1.z-point0.z)
        length = abs(point1.x-point0.x)

        # Determining frame placement
        x = (point0.x if placement == 'start'
             else point0.x + length if placement == 'end' else point0.x + length / 2.0 if placement == 'mid' else 0)
        y = (width / 2.0) + point0.y
        z = point0.z
        position = Position(Point(x, y, z))

        # Instantiating the frame
        frame = FFrame(width, height, position)

        # Placing parameters used to create the frame into a dictionary for reference/debugging
        param_dict = {'width': width,
                      'height': height,
                      'length': length,
                      'position': position}

        return [frame, param_dict]

    @staticmethod
    def bbox_extractor(sizing_components):
        """ Obtains the bbox from a group of TopoDShapes and returns the resultant bbox

        :param sizing_components:
        :return: Bound-box of Input Parts
        :rtype: bbox
        """
        shape_out = None
        if type(sizing_components) == list:
            if len(sizing_components) > 1:
                shape_in = sizing_components[0].internal_shape
                for i in range(0, len(sizing_components) - 1):
                    new_part = Fused(shape_in=shape_in, tool=sizing_components[i+1].internal_shape)
                    shape_in = new_part
                shape_out = shape_in
            elif len(sizing_components) <= 1:
                shape_out = sizing_components.internal_shape
        else:
            shape_out = sizing_components.internal_shape
        return shape_out.bbox


if __name__ == '__main__':
    from parapy.gui import display

    obj = Fuselage()
    display(obj)

