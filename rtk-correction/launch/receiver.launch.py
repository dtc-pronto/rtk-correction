from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():

    args = [
        # Rajant -- primary data path, static/known address, connected immediately
        DeclareLaunchArgument('rajant_ip', default_value='10.10.10.10'),
        DeclareLaunchArgument('rtk_port', default_value='7501'),
        DeclareLaunchArgument('wifi_info_port', default_value='7502'),

        # WiFi discovery -- learned WiFi endpoint first, then subnet scan fallback
        DeclareLaunchArgument('wifi_scan_subnet', default_value=''),

        # Hysteresis for deciding when Rajant is effectively stale
        DeclareLaunchArgument('rajant_stale_timeout', default_value='5.0'),
        DeclareLaunchArgument('wifi_stale_timeout', default_value='5.0'),
        DeclareLaunchArgument('rajant_probe_interval', default_value='2.0'),
    ]

    node = Node(
        package='rtk_correction',
        executable='receiver',
        name='rtk_receiver',
        output='screen',
        emulate_tty=True,
        parameters=[{
            'rajant_ip': LaunchConfiguration('rajant_ip'),
            'rtk_port': LaunchConfiguration('rtk_port'),
            'wifi_info_port': LaunchConfiguration('wifi_info_port'),
            'wifi_scan_subnet': LaunchConfiguration('wifi_scan_subnet'),
            'rajant_stale_timeout': LaunchConfiguration('rajant_stale_timeout'),
            'wifi_stale_timeout': LaunchConfiguration('wifi_stale_timeout'),
            'rajant_probe_interval': LaunchConfiguration('rajant_probe_interval'),
        }],
    )

    return LaunchDescription(args + [node])
