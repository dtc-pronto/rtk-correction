from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

def generate_launch_description():

    ip_arg = DeclareLaunchArgument('ip', default_value='10.10.10.10')
    port_arg = DeclareLaunchArgument('port', default_value='7507')

    ip_lc = LaunchConfiguration('ip')
    port_lc = LaunchConfiguration('port')

    node = Node(package='rtk_correction',
                executable='broadcaster',
                name='rtk_broadcaster',
                output='screen',
                emulate_tty=True,
                parameters=[{'ip': ip_lc, 'port': port_lc}])

    return LaunchDescription([ip_arg, port_arg, node])


