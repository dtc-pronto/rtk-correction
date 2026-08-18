from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():

    args = [
        # Rajant -- primary path, static/known address
        DeclareLaunchArgument('ip', default_value='10.10.10.10'),
        DeclareLaunchArgument('port', default_value='7507'),
        DeclareLaunchArgument('rajant_interface', default_value='rajant'),

        # WiFi -- warm standby, address discovered at runtime
        DeclareLaunchArgument('wifi_interface', default_value='wlan0'),
        DeclareLaunchArgument('beacon_port', default_value='7508'),
        DeclareLaunchArgument('beacon_interval', default_value='1.5'),

        # Health check -- pings a known peer (e.g. the rover's Rajant IP)
        # over the Rajant interface specifically. Leave ping_target empty
        # to disable the health check (Rajant will be assumed healthy and
        # WiFi will never carry real corrections).
        DeclareLaunchArgument('ping_target', default_value=''),
        DeclareLaunchArgument('ping_interval', default_value='1.5'),
        DeclareLaunchArgument('ping_timeout', default_value='1.0'),
        DeclareLaunchArgument('fail_threshold', default_value='3'),
        DeclareLaunchArgument('recover_threshold', default_value='3'),
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
            'rajant_interface': LaunchConfiguration('rajant_interface'),
            'wifi_interface': LaunchConfiguration('wifi_interface'),
            'beacon_port': LaunchConfiguration('beacon_port'),
            'beacon_interval': LaunchConfiguration('beacon_interval'),
            'ping_target': LaunchConfiguration('ping_target'),
            'ping_interval': LaunchConfiguration('ping_interval'),
            'ping_timeout': LaunchConfiguration('ping_timeout'),
            'fail_threshold': LaunchConfiguration('fail_threshold'),
            'recover_threshold': LaunchConfiguration('recover_threshold'),
        }],
    )

    return LaunchDescription(args + [node])
