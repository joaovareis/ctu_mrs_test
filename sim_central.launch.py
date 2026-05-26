import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import ExecuteProcess, IncludeLaunchDescription, SetEnvironmentVariable, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():

    # 1. Configuração das Variáveis de Ambiente (equivalente ao pre_window)
    env_vars = [
        SetEnvironmentVariable('UAV_NAME', 'uav1'),
        SetEnvironmentVariable('RUN_TYPE', 'simulation'),
        SetEnvironmentVariable('UAV_TYPE', 'x500'),
        SetEnvironmentVariable('RMW_IMPLEMENTATION', 'rmw_zenoh_cpp'),
        SetEnvironmentVariable('USE_SIM_TIME', 'true'),
        SetEnvironmentVariable('ZENOH_ROUTER_CHECK_ATTEMPTS', '30'),
    ]

    # 2. Zenoh Router
    zenoh_router = ExecuteProcess(
        cmd=['ros2', 'run', 'rmw_zenoh_cpp', 'rmw_zenohd'],
        output='log'
    )

    # 3. Gazebo Simulator
    # Nota: Ajuste o nome do pacote se 'mrs_uav_gazebo_simulator' tiver outro nome instalado
    gazebo_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            os.path.join(get_package_share_directory('mrs_uav_gazebo_simulator'), 'launch', 'simulation.launch.py')
        ]),
        launch_arguments={'spawner_config': './config/spawner_config.yaml'}.items()
    )

    # Câmera tracking (Executa após o Gazebo subir)
    # gazebo_camera_track = ExecuteProcess(
    #     cmd=['bash', '-c', 'waitForGazebo && sleep 2; gz topic -t /gui/track -m gz.msgs.CameraTrack -p "track_mode: 2 follow_target { name: \\"$UAV_NAME\\" }"'],
    #     output='screen'
    # )

    # 4. Status Panel
    # mrs_status = ExecuteProcess(
    #     cmd=['ros2', 'run', 'mrs_uav_status', 'status.sh'],
    #     output='screen'
    # )

    # 5. Spawner (Injeta o export do Zenoh antes de chamar o serviço)
    spawn_drone = ExecuteProcess(
        cmd=['bash', '-c', """export RMW_IMPLEMENTATION=rmw_zenoh_cpp && waitForGazebo && ros2 service call /mrs_drone_spawner/spawn mrs_msgs/srv/String "{value: '1 --x500 --enable-ground-truth --enable-rangefinder --enable-bluefox-camera-down'}" """],
        output='log'
    )

    # 6. Hardware API (PX4 Bridge)
    hw_api = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            os.path.join(get_package_share_directory('mrs_uav_px4_api'), 'launch', 'api.launch.py')
        ])
    )

    # Adicionando o delay de 6 segundos conforme seu script original do tmux
    hw_api_delayed = TimerAction(period=6.0, actions=[hw_api])

    # 7. MRS Core (Versão nativa comentada, caso queira usar no futuro)
    # mrs_core = IncludeLaunchDescription(
    #     PythonLaunchDescriptionSource([
    #         os.path.join(get_package_share_directory('mrs_uav_core'), 'launch', 'core.launch.py')
    #     ]),
    #     launch_arguments={
    #         'platform_config': './config/platform_config.yaml',
    #         'custom_config': './config/custom_config.yaml',
    #         'world_config': './config/world_config.yaml',
    #         'network_config': './config/network_config.yaml'
    #     }.items()
    # )

    # 7. MRS Core (Injeta o export do Zenoh)
    mrs_core_wrapped = ExecuteProcess(
        cmd=['bash', '-c', 'export RMW_IMPLEMENTATION=rmw_zenoh_cpp && waitForHwApi && ros2 launch mrs_uav_core core.launch.py platform_config:=./config/platform_config.yaml custom_config:=./config/custom_config.yaml world_config:=./config/world_config.yaml network_config:=./config/network_config.yaml'],
        output='log'
    )

    # 8. Autostart (Injeta o export do Zenoh)
    autostart = ExecuteProcess(
        cmd=['bash', '-c', 'export RMW_IMPLEMENTATION=rmw_zenoh_cpp && waitForCore && ros2 launch mrs_uav_autostart automatic_start.launch.py custom_config:=./config/automatic_start.yaml'],
        output='log'
    )

    # 9. Takeoff e Goto scripts locais (Injeta o export do Zenoh)
    takeoff_script = ExecuteProcess(
        cmd=['bash', '-c', 'export RMW_IMPLEMENTATION=rmw_zenoh_cpp && waitForCore && sleep 6 && ./takeoff.sh'],
        output='screen'
    )

    goto_script = ExecuteProcess(
        cmd=['bash', '-c', 'export RMW_IMPLEMENTATION=rmw_zenoh_cpp && waitForTakeoff && ./goto.py'],
        output='screen'
    )

    # 10. RViz2
    # rviz = ExecuteProcess(
    #     cmd=['bash', '-c', 'export RMW_IMPLEMENTATION=rmw_zenoh_cpp && waitForCore && ros2 run rviz2 rviz2 -d ./rviz.rviz --ros-args -p use_sim_time:=true'],
    #     output='screen'
    # )

    # 11. Layout Manager
    # layout_manager = ExecuteProcess(
    #     cmd=['bash', '-c', 'waitForCore && sleep 2; ~/.i3/layout_manager.sh ./layout.json'],
    #     output='log'
    # )

    # Montando a descrição final
    ld = LaunchDescription()

    # Adicionar variáveis de ambiente primeiro
    for var in env_vars:
        ld.add_action(var)

    # Adicionar os processos/nós ativos
    ld.add_action(zenoh_router)
    ld.add_action(gazebo_sim)
    # ld.add_action(gazebo_camera_track)
    # ld.add_action(mrs_status)
    ld.add_action(spawn_drone)
    ld.add_action(hw_api_delayed)
    ld.add_action(mrs_core_wrapped)
    ld.add_action(autostart)
    ld.add_action(takeoff_script)
    ld.add_action(goto_script)
    # ld.add_action(rviz)
    # ld.add_action(layout_manager)

    return ld