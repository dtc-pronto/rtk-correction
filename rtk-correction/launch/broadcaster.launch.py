from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():

    args = [
        # Rajant -- primary path, static/known address
        DeclareLaunchArgument('rajant_ip', default_value='10.10.10.10'),
        DeclareLaunchArgument('rtk_port', default_value='7501'),
        DeclareLaunchArgument('wifi_info_port', default_value='7502'),

        # WiFi -- standby path, address discovered at runtime
        DeclareLaunchArgument('wifi_interface', default_value='wlan0'),
    ]

    node = Node(
        package='rtk_correction',
        executable='broadcaster',
        name='rtk_broadcaster',
        output='screen',
        emulate_tty=True,
        parameters=[{
            'rajant_ip': LaunchConfiguration('rajant_ip'),
            'rtk_port': LaunchConfiguration('rtk_port'),
            'wifi_info_port': LaunchConfiguration('wifi_info_port'),
            'wifi_interface': LaunchConfiguration('wifi_interface'),
        }],
    )

    return LaunchDescription(args + [node])
