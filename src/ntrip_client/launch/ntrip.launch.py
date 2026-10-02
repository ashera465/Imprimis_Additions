from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():

    #Note the simulation is deprecated.
    sim_arg = DeclareLaunchArgument(
        'sim',
        default_value='false',
        description='Launch the simulated GPS publisher as well as the NTRIP client.',
    )

    return LaunchDescription([
        sim_arg,
        Node(
            package='ntrip_client',
            executable='ntrip_node',
            name='ntrip_client',
            output='screen',
        ),
        Node(
            package='ntrip_client',
            executable='simulated_gps_node',
            name='simulated_gps',
            output='screen',
            condition=IfCondition(LaunchConfiguration('sim')),
        ),
    ])
