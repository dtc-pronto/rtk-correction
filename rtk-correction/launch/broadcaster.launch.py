from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():

    args = [
        # Rajant -- primary path, static/known address
        DeclareLaunchArgument('ip', default_value='10.10.10.10'),
        DeclareLaunchArgument('port', default_value='7507'),
        DeclareLaunchArgument('wifi_info_port', default_value='7509'),
        DeclareLaunchArgument('rajant_interface', default_value='rajant'),

        # WiFi -- standby path, address discovered at runtime
        DeclareLaunchArgument('wifi_interface', default_value='wlan0'),
        DeclareLaunchArgument('beacon_port', default_value='7508'),
        DeclareLaunchArgument('beacon_interval', default_value='1.5'),
    ]

    node = Node(
        package='rtk_correction',
        executable='broadcaster',
        name='rtk_broadcaster',
        output='screen',
        emulate_tty=True,
        parameters=[{
            'ip': LaunchConfiguration('ip'),
            'port': LaunchConfiguration('port'),
            'wifi_info_port': LaunchConfiguration('wifi_info_port'),
            'rajant_interface': LaunchConfiguration('rajant_interface'),
            'wifi_interface': LaunchConfiguration('wifi_interface'),
            'beacon_port': LaunchConfiguration('beacon_port'),
            'beacon_interval': LaunchConfiguration('beacon_interval'),
        }],
    )

    return LaunchDescription(args + [node])
