from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():

    args = [
        # Rajant -- primary data path, static/known address, connected immediately
        DeclareLaunchArgument('ip', default_value='10.10.10.10'),
        DeclareLaunchArgument('port', default_value='7507'),
        DeclareLaunchArgument('wifi_info_port', default_value='7509'),

        # WiFi discovery -- fast beacon, then learned WiFi endpoint, then subnet scan
        DeclareLaunchArgument('beacon_port', default_value='7508'),
        DeclareLaunchArgument('beacon_wait_timeout', default_value='8.0'),
        DeclareLaunchArgument('wifi_scan_subnet', default_value=''),

        # Hysteresis for deciding when Rajant is effectively stale
        DeclareLaunchArgument('rajant_stale_timeout', default_value='5.0'),
        DeclareLaunchArgument('rajant_probe_interval', default_value='1.0'),
        DeclareLaunchArgument('wifi_retry_timeout', default_value='2.0'),
        DeclareLaunchArgument('stale_timeout', default_value='5.0'),
    ]

    node = Node(
        package='rtk_correction',
        executable='receiver',
        name='rtk_receiver',
        output='screen',
        emulate_tty=True,
        parameters=[{
            'ip': LaunchConfiguration('ip'),
            'port': LaunchConfiguration('port'),
            'wifi_info_port': LaunchConfiguration('wifi_info_port'),
            'beacon_port': LaunchConfiguration('beacon_port'),
            'beacon_wait_timeout': LaunchConfiguration('beacon_wait_timeout'),
            'wifi_scan_subnet': LaunchConfiguration('wifi_scan_subnet'),
            'rajant_stale_timeout': LaunchConfiguration('rajant_stale_timeout'),
            'rajant_probe_interval': LaunchConfiguration('rajant_probe_interval'),
            'wifi_retry_timeout': LaunchConfiguration('wifi_retry_timeout'),
            'stale_timeout': LaunchConfiguration('stale_timeout'),
        }],
    )

    return LaunchDescription(args + [node])
