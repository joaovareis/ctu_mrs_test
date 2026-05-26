import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import ExecuteProcess, IncludeLaunchDescription, SetEnvironmentVariable, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from launch.substitutions import PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare
from launch_ros.actions import ComposableNodeContainer
from launch_ros.descriptions import ComposableNode

def generate_launch_description():
    ld = LaunchDescription()

    set_uav_type = SetEnvironmentVariable(name='UAV_TYPE', value='f450')
    set_run_type = SetEnvironmentVariable(name='RUN_TYPE', value='simulation')
    set_zenoh_config = SetEnvironmentVariable(name='ZENOH_CONFIG', value='/root/ros2_ws/zenoh_config.json')

    #my_autostart_config = PathJoinSubstitution([FindPackageShare('imav_26'), 'config', 'automatic_start.yaml'])
    my_world_config     = PathJoinSubstitution([FindPackageShare('imav_26'), 'config', 'world_config.yaml'])
    my_network_config   = PathJoinSubstitution([FindPackageShare('imav_26'), 'config', 'network_config.yaml'])
    my_custom_config    = PathJoinSubstitution([FindPackageShare('imav_26'), 'config', 'custom_config.yaml'])
    my_spawner_config   = PathJoinSubstitution([FindPackageShare('imav_26'), 'config', 'spawner.yaml'])
    my_platform_config  = PathJoinSubstitution([FindPackageShare('imav_26'), 'config', 'x500.yaml'])

    zenoh_router = ExecuteProcess(
        cmd=['ros2', 'run', 'rmw_zenoh_cpp', 'rmw_zenohd', '--config', '/root/ros2_ws/zenoh_config.json'],
        output='screen'
    )
    
    mrs_simulation = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            PathJoinSubstitution([
                FindPackageShare('mrs_uav_gazebo_simulator'),
                'launch',
                'simulation.launch.py'
            ])
        ]),
        launch_arguments={
            'spawner_config': my_spawner_config,
            #'world_file' :
        }.items()
    )

    mrs_core = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            PathJoinSubstitution([
                FindPackageShare('mrs_uav_core'),
                'launch',
                'core.launch.py'
            ])
        ]),
        launch_arguments={
            'uav_name': 'uav1',
            'use_sim_time': 'true',
            'world_config': my_world_config,
            'network_config': my_network_config,
            'uav_type': 'f450',
            #'uav_mass': '0.0427',
            'uav_mass': '1.7',

            'platform_config': my_platform_config,
            'custom_config': my_custom_config,
            'all_outputs_enabled_by_default': 'true',
        }.items()
    )

    hw_api = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            os.path.join(get_package_share_directory('mrs_uav_px4_api'), 'launch', 'api.launch.py')
        ]),

        launch_arguments={
            'use_sim_time': 'true',
        }.items()
    )

    spawn_drone_service = ExecuteProcess(
        cmd=[
            'ros2', 'service', 'call', 
            '/mrs_drone_spawner/spawn', 
            'mrs_msgs/srv/String', 
            "{value: '1 --f450 --enable-ground-truth --enable-rangefinder'}"
        ],
        output='screen'
    )

    mrs_autostart_container = ComposableNodeContainer(
        name='automatic_start_container',
        namespace='uav1',
        package='rclcpp_components',
        executable='component_container',
        composable_node_descriptions=[
            ComposableNode(
                package='mrs_uav_autostart',
                plugin='mrs_uav_autostart::automatic_start::AutomaticStart',
                name='automatic_start',
                namespace='uav1',
                parameters=[
                    PathJoinSubstitution([FindPackageShare('mrs_uav_autostart'), 'config', 'public', 'automatic_start.yaml']),
                    PathJoinSubstitution([FindPackageShare('mrs_uav_autostart'), 'config', 'private', 'automatic_start.yaml']),
                    PathJoinSubstitution([FindPackageShare('imav_26'), 'config', 'automatic_start.yaml']),
                    {
                        'use_sim_time': True,
                        'uav_name': 'uav1',
                        'simulation': True,
                        'custom_config': PathJoinSubstitution([FindPackageShare('imav_26'), 'config', 'automatic_start.yaml']),
                        'config_private': PathJoinSubstitution([FindPackageShare('mrs_uav_autostart'), 'config', 'private', 'automatic_start.yaml']),
                        'config_public': PathJoinSubstitution([FindPackageShare('mrs_uav_autostart'), 'config', 'public', 'automatic_start.yaml'])
                    }
                ]
            )
        ],
        output='screen',
    )

    # Automated Flight Sequence Actions

    zenoh_env = {'RMW_IMPLEMENTATION': 'rmw_zenoh_cpp'}
    
    arm_drone = ExecuteProcess(
        cmd=['ros2', 'service', 'call', '/uav1/hw_api/arming', 'std_srvs/srv/SetBool', '{data: true}'],
        additional_env=zenoh_env,
        output='screen'
    )
    
    activate_midair = ExecuteProcess(
        cmd=['ros2', 'service', 'call', '/uav1/uav_manager/midair_activation', 'std_srvs/srv/Trigger'],
        output='screen'
    )

    #takeoff_drone = ExecuteProcess(
    #    cmd=['ros2', 'service', 'call', '/uav1/uav_manager/takeoff', 'std_srvs/srv/Trigger'],
    #    output='screen'
    #)

    takeoff_drone = ExecuteProcess(
        cmd=['ros2', 'service', 'call', '/uav1/control_manager/goto_fcu', 'mrs_msgs/srv/Vec4', '{goal: [0.0, 0.0, 2.5, 0.0]}'],
        additional_env=zenoh_env,
        output='screen'
    )

    delay_sim = TimerAction(
        period=8.0,
        actions=[mrs_simulation]
    )

    delay_spawn = TimerAction(
        period=13.0,
        actions=[spawn_drone_service]
    )

    delay_hw_api = TimerAction(
        period=21.0,
        actions=[hw_api]
    )

    delay_mrs_core = TimerAction(
        period=30.0,
        actions=[mrs_core]
    )

    delay_autostart = TimerAction(
        period=60.0,
        actions=[mrs_autostart_container]
    )

    delay_arm = TimerAction(period=65.0, actions=[arm_drone])
    delay_midair = TimerAction(period=70.0, actions=[activate_midair])
    delay_takeoff = TimerAction(period=80.0, actions=[takeoff_drone])

    ld.add_action(set_zenoh_config)
    ld.add_action(set_uav_type)
    ld.add_action(set_run_type)
    ld.add_action(zenoh_router)
    ld.add_action(delay_sim)
    ld.add_action(delay_spawn)
    ld.add_action(delay_hw_api)
    ld.add_action(delay_mrs_core)
    #ld.add_action(delay_autostart)

    ld.add_action(delay_arm)
    ld.add_action(delay_midair)
    ld.add_action(delay_takeoff)

    return ld

    