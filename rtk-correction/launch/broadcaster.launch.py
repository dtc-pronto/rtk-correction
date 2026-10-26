from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    log_level_arg = DeclareLaunchArgument('log_level', default_value='info')
    # Rajant -- primary path, static/known address
    basestation_rajant_ip_arg = DeclareLaunchArgument('basestation_rajant_ip', default_value='10.10.10.10')
    rtk_port_arg = DeclareLaunchArgument('rtk_port', default_value='7501')
    wifi_info_port_arg = DeclareLaunchArgument('wifi_info_port', default_value='7502')
    # WiFi -- standby path, address discovered at runtime
    wifi_interface_arg = DeclareLaunchArgument('wifi_interface', default_value='wlan0')
   
    broadcaster_node = Node(
            package='rtk_correction',
            executable='broadcaster',
            name='rtk_broadcaster',
            arguments=['--ros-args', '--log-level', LaunchConfiguration('log_level')],
            emulate_tty=True,
            parameters=[{
                'basestation_rajant_ip': LaunchConfiguration('basestation_rajant_ip'),
                'rtk_port': LaunchConfiguration('rtk_port'),
                'wifi_info_port': LaunchConfiguration('wifi_info_port'),
                'wifi_interface': LaunchConfiguration('wifi_interface'),
            }],
            output='screen',
        )

    return LaunchDescription([
        log_level_arg,
        basestation_rajant_ip_arg,
        rtk_port_arg,
        wifi_info_port_arg,
        wifi_interface_arg,
        broadcaster_node,
    ])