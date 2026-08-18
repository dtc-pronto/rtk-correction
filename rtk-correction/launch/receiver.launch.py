from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():

    args = [
        # Rajant -- primary path, static/known address, connected immediately
        DeclareLaunchArgument('ip', default_value='10.10.10.10'),
        DeclareLaunchArgument('port', default_value='7507'),

        # WiFi discovery -- beacon first (fast), block scan as a fallback
        # if no beacon is heard (e.g. broadcast blocked on the network).
        # wifi_scan_subnet must be set (e.g. "192.168.1.0/24") for the
        # scan fallback to be used at all; left empty, scanning is skipped.
        DeclareLaunchArgument('beacon_port', default_value='7508'),
        DeclareLaunchArgument('beacon_wait_timeout', default_value='8.0'),
        DeclareLaunchArgument('wifi_scan_subnet', default_value=''),

        # How long with no corrections at all before flagging the link as stale
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
            'beacon_port': LaunchConfiguration('beacon_port'),
            'beacon_wait_timeout': LaunchConfiguration('beacon_wait_timeout'),
            'wifi_scan_subnet': LaunchConfiguration('wifi_scan_subnet'),
            'stale_timeout': LaunchConfiguration('stale_timeout'),
        }],
    )

    return LaunchDescription(args + [node])
