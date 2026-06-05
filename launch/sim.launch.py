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
    
    pkg_share_imav = FindPackageShare('imav_26')

    my_zenoh_config = PathJoinSubstitution([pkg_share_imav, 'config', 'zenoh_config.json'])

    set_uav_type = SetEnvironmentVariable(name='UAV_TYPE', value='f450')
    set_run_type = SetEnvironmentVariable(name='RUN_TYPE', value='simulation')
    set_rmw_zenoh = SetEnvironmentVariable(name='RMW_IMPLEMENTATION', value='rmw_zenoh_cpp')
    set_zenoh_config = SetEnvironmentVariable(name='ZENOH_CONFIG', value=my_zenoh_config)
    #my_autostart_config = PathJoinSubstitution([FindPackageShare('imav_26'), 'config', 'automatic_start.yaml'])
    my_world_config     = PathJoinSubstitution([FindPackageShare('imav_26'), 'config', 'world_config.yaml'])
    my_network_config   = PathJoinSubstitution([FindPackageShare('imav_26'), 'config', 'network_config.yaml'])
    my_custom_config    = PathJoinSubstitution([FindPackageShare('imav_26'), 'config', 'custom_config.yaml'])
    my_spawner_config   = PathJoinSubstitution([FindPackageShare('imav_26'), 'config', 'spawner.yaml'])
    my_platform_config  = PathJoinSubstitution([FindPackageShare('imav_26'), 'config', 'f450.yaml'])

    zenoh_router = ExecuteProcess(
        cmd=['ros2', 'run', 'rmw_zenoh_cpp', 'rmw_zenohd', '--config', my_zenoh_config],
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
            # ORDEM ESTRITA: ID MODELO X Y Z YAW FLAGS
            'value: "1 f450 --pos 0 0 0.5 0 --enable-ground-truth --enable-rangefinder"'
        ],
        output='screen'
    )

    automatic_start_simples = Node(
        package='mrs_uav_autostart',
        executable='automatic_start',  # Chama o binário direto, sem container
        name='automatic_start',
        namespace='uav1',
        output='screen',
        parameters=[
            PathJoinSubstitution([FindPackageShare('mrs_uav_autostart'), 'config', 'public', 'automatic_start.yaml']),
            PathJoinSubstitution([FindPackageShare('mrs_uav_autostart'), 'config', 'private', 'automatic_start.yaml']),
            PathJoinSubstitution([FindPackageShare('imav_26'), 'config', 'automatic_start.yaml']),
            {
                'uav_name': 'uav1',
                'simulation': True,
                'use_sim_time': True,
            }
        ],
        remappings=[
            ('/uav1/automatic_start/estimation_diag_in', '/uav1/estimation_manager/diagnostics'),
            ('/uav1/automatic_start/control_manager_diagnostics_in', '/uav1/control_manager/diagnostics'),
            ('/uav1/automatic_start/uav_manager_diagnostics_in', '/uav1/uav_manager/diagnostics'),
            ('/uav1/automatic_start/hw_api_status_in', '/uav1/hw_api/status'),
            ('/uav1/automatic_start/hw_api_capabilities_in', '/uav1/hw_api/capabilities'),
            ('/uav1/automatic_start/gazebo_spawner_diagnostics_in', '/mrs_drone_spawner/diagnostics'),
            
            ('/uav1/automatic_start/arm_out', '/uav1/hw_api/arming'),
            ('/uav1/automatic_start/takeoff_out', '/uav1/uav_manager/takeoff'),
            ('/uav1/automatic_start/toggle_control_output_out', '/uav1/control_manager/toggle_output'),
        ]
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

    #takeoff_drone = ExecuteProcess(
    #    cmd=['ros2', 'service', 'call', '/uav1/control_manager/goto_fcu', 'mrs_msgs/srv/Vec4', '{goal: [0.0, 0.0, 2.5, 0.0]}'],
    #    additional_env=zenoh_env,
    #    output='screen'
    #)

    python_script = Node(
        package='imav_26',
        executable='test2.py',
        name='test_node',
        namespace='uav1',
        output='screen',
        parameters=[{'use_sim_time': True}],
        additional_env=zenoh_env,
    )

    delay_sim = TimerAction(
        period=3.0,
        actions=[mrs_simulation]
    )

    delay_spawn = TimerAction(
        period=10.0,
        actions=[spawn_drone_service]
    )

    delay_hw_api = TimerAction(
        period=18.0,
        actions=[hw_api]
    )

    delay_mrs_core = TimerAction(
        period=28.0,
        actions=[mrs_core]
    )

    delay_autostart = TimerAction(
        period=48.0,
        actions=[automatic_start_simples]
    )

    delay_arm = TimerAction(period=65.0, actions=[arm_drone])
    delay_midair = TimerAction(period=70.0, actions=[activate_midair])
    #delay_takeoff = TimerAction(period=80.0, actions=[takeoff_drone])
    delay_test = TimerAction(period=56.0, actions=[python_script])    

    ld.add_action(set_rmw_zenoh)
    ld.add_action(set_zenoh_config)
    ld.add_action(set_uav_type)
    ld.add_action(set_run_type)
    ld.add_action(zenoh_router)
    ld.add_action(delay_sim)
    ld.add_action(delay_spawn)
    ld.add_action(delay_hw_api)
    ld.add_action(delay_mrs_core)
    #ld.add_action(delay_autostart)

    #ld.add_action(delay_arm)
    #ld.add_action(delay_midair)
    #ld.add_action(delay_takeoff)
    ld.add_action(delay_autostart)

    return ld

    