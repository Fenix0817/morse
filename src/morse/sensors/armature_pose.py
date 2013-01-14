import logging; logger = logging.getLogger("morse." + __name__)
import math
import morse.core.sensor
from morse.core.services import service, async_service, interruptible
from morse.core import blenderapi
from morse.helpers.components import add_property

class ArmaturePose(morse.core.sensor.Sensor):
    """
    The sensor streams the joint state (ie, the rotation or translation value
    of each joint belonging to the armature) of its parent armature.

    .. note::

        This sensor **must** be added as a child of the armature
        you want to sense, like in the example below:

        .. code-block:: python

            robot = ATRV()

            arm = KukaLWR()
            robot.append(arm)
            arm.translate(z=0.9)

            arm_pose = ArmaturePose('arm_pose')
            arm.append(arm_pose)

    This component only allows to *read* armature configuration. To change the
    armature pose, you need an :doc:`armature actuator <../sensors/armature>`.

    .. important:: 
    
        To be valid, special care must be given when creating armatures. If you
        want to add new one, please carefully read the :doc:`armature creation
        <../../dev/armature_creation>` documentation.


    .. note::

        The data structure on datastream exported by the armature sensor
        depends on the armature.  It is a dictionary of pair `(joint name,
        joint value)`.  Joint values are either radians (for revolute joints)
        or meters (for prismatic joints)


    :sees: :doc:`armature actuator <../actuators/armature>`
    """
    _name = "Armature Pose Sensor"
    _short_desc = "Returns the joint state of a MORSE armature"

    def __init__(self, obj, parent=None):
        """ Constructor method.

        Receives the reference to the Blender object.
        The second parameter should be the name of the object's parent.
        """
        logger.info('%s initialization' % obj.name)
        # Call the constructor of the parent class
        super(self.__class__,self).__init__(obj, parent)

        self.armature = self._get_armature(self.blender_obj)
        if not self.armature:
            logger.error("The armature pose sensor has not been parented to an armature! " + \
                    "This sensor must be a child of an armature. Check you scene.")
            return

        logger.debug("Found armature <%s>" % self.armature.name)

        self._armature_actuator = None

        # Define the variables in 'local_data'
        for channel in self.armature.channels:
            self.local_data[channel.name] = 0.0

        logger.info('Component <%s> initialized' % self.blender_obj.name)

    def _get_armature(self, obj):
        if hasattr(obj, "channels"):
            return obj
        elif not obj.parent:
            return None
        else:
            return self._get_armature(obj.parent)

    def _get_armature_actuator(self):
        # Get the reference to the class instance of the armature actuator
        component_dict = blenderapi.persistantstorage().componentDict
        if self.armature and self.armature.name in component_dict:
            self._armature_actuator = component_dict[self.armature.name]

    @service
    def get_joints(self):
        """
        Returns the list of joints of the armature.

        :return: the (ordered) list of joints in the armature, from root to tip.
        """
        return [c.name for c in self.armature.channels]

    @service
    def get_state(self):
        """
        Returns the joint state of the armature, ie a dictionnary with joint names as key and the corresponding rotation or translation as value (respectively in radian or meters).
        """
        joints = {}
        # get the rotation of each channel
        for channel in self.armature.channels:
            joints[channel.name] = self.get_joint(channel.name)

        return joints

    @service
    def get_joint(self, joint):
        """
        Returns the *value* of a given joint, either:
        - its absolute rotation in radian along its rotation axis, or
        - it absolute translation in meters along its translation axis.

        Throws an exception if the joint does not exist.

        :param joint: the name of the joint in the armature.
        """
        if not self._armature_actuator:
            self._get_armature_actuator()

        armature_actuator = self._armature_actuator

        channel, is_prismatic = armature_actuator._get_joint(joint) # reuse helper functions from armature actuator

        # Retrieve the motion axis
        axis_index = next(i for i, j in enumerate(armature_actuator.find_dof(channel)) if j)

        if is_prismatic:
            return channel.head_pose[axis_index]
        else: # revolute joint
            return channel.joint_rotation[axis_index]

    @service
    def get_joints_length(self):
        """
        Returns a dict with the armature joints' names as key and
        and the corresponding bone length as value (in meters).
        """
        lengths_dict = {}
        for channel in self.armature.channels:
            # find the length of the current channel
            #head = channel.pose_head
            #tail = channel.pose_tail
            diff = channel.pose_head - channel.pose_tail
            length = math.sqrt(diff[0]**2 + diff[1]**2 + diff[2]**2)
            lengths_dict[channel.name] = length
        return lengths_dict

    def default_action(self):
        """ Get the x, y, z, yaw, pitch and roll of the armature,
        and the rotation angle for each of the segments. """

        if not self.armature:
            return
        if not self._armature_actuator:
            self._get_armature_actuator()

        # Check all the segments of the armature
        for channel in self.armature.channels:
            segment_angle = channel.joint_rotation

            # Use the corresponding direction for each rotation
            #  taken directly from the armature instance
            if self._armature_actuator._dofs[channel.name][1] == 1:
                self.local_data[channel.name] = segment_angle[1]
            elif self._armature_actuator._dofs[channel.name][2] == 1:
                self.local_data[channel.name] = segment_angle[2]
