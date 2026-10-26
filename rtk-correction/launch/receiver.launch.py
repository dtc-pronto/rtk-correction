from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    log_level_arg = DeclareLaunchArgument('log_level', default_value='info')

    # Network parameters
    basestation_rajant_ip_arg = DeclareLaunchArgument('basestation_rajant_ip', default_value='10.10.10.10')
    rtk_port_arg = DeclareLaunchArgument('rtk_port', default_value='7501')
    wifi_info_port_arg = DeclareLaunchArgument('wifi_info_port', default_value='7502')
    basestation_wifi_ip_arg = DeclareLaunchArgument('basestation_wifi_ip', default_value='192.168.60.10')
    
    # Hysteresis for deciding when Rajant is effectively stale
    rajant_stale_timeout_arg = DeclareLaunchArgument('rajant_stale_timeout', default_value='5.0')
    wifi_stale_timeout_arg = DeclareLaunchArgument('wifi_stale_timeout', default_value='5.0')
    rajant_probe_interval_arg = DeclareLaunchArgument('rajant_probe_interval', default_value='4.0')
    wifi_probe_interval_arg = DeclareLaunchArgument('wifi_probe_interval', default_value='4.0')

   
    receiver_node = Node(
            package='rtk_correction',
            executable='receiver',
            name='rtk_receiver',
            output='screen',
            arguments=['--ros-args', '--log-level', LaunchConfiguration('log_level')],
            emulate_tty=True,
            parameters=[{
                'basestation_rajant_ip': LaunchConfiguration('basestation_rajant_ip'),
                'rtk_port': LaunchConfiguration('rtk_port'),
                'wifi_info_port': LaunchConfiguration('wifi_info_port'),
                'basestation_wifi_ip': LaunchConfiguration('basestation_wifi_ip'),
                'rajant_stale_timeout': LaunchConfiguration('rajant_stale_timeout'),
                'wifi_stale_timeout': LaunchConfiguration('wifi_stale_timeout'),
                'rajant_probe_interval': LaunchConfiguration('rajant_probe_interval'),
                'wifi_probe_interval': LaunchConfiguration('wifi_probe_interval'),
            }],
        )

    return LaunchDescription([
        log_level_arg,
        basestation_rajant_ip_arg,
        rtk_port_arg,
        basestation_wifi_ip_arg,
        wifi_info_port_arg,
        rajant_stale_timeout_arg,
        wifi_stale_timeout_arg,
        rajant_probe_interval_arg,
        wifi_probe_interval_arg,
        receiver_node,
    ])
