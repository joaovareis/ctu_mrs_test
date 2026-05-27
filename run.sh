#!/bin/bash

# Caminho para a raiz do projeto
PROJECT_ROOT=$(dirname "$(realpath "$0")")

# Nome da imagem Docker
IMAGE_NAME="imav_26"

# Nome do contêiner
CONTAINER_NAME="imav_26_container"

# Path para guardar o catkin_ws no host
HOST_ROS2_WS_PATH="$PROJECT_ROOT/$CONTAINER_NAME/ros2_ws"

echo "Configurando permissões do servidor X..."
xhost +local:root > /dev/null

# --- Detecção de GPU unificada ---
if [ -z "$(lspci | grep -i nvidia)" ]; then
    USE_GPUS=""
    NVIDIA_ENV=""
    echo "NVIDIA GPU NÃO detectada. Usando renderização padrão."
else
    # Adicionando o runtime nativo da nvidia para parear perfeitamente com o CachyOS
    USE_GPUS="--gpus all --runtime=nvidia"
    NVIDIA_ENV="--env=NVIDIA_VISIBLE_DEVICES=all \
                --env=NVIDIA_DRIVER_CAPABILITIES=all,graphics,utility,compute \
                --env=__NV_PRIME_RENDER_OFFLOAD=1 \
                --env=__GLX_VENDOR_LIBRARY_NAME=nvidia"
    echo "NVIDIA GPU detectada. Render Offload e Runtime Nvidia ativados."
fi

if [ ! -d "$HOST_ROS2_WS_PATH" ] || [ -z "$(ls -A "$HOST_ROS2_WS_PATH" 2>/dev/null)" ]; then
    echo "Primeira execução detectada. Criando container temporário para workspace ROS2..."
    
    docker run -d --name temp_container \
        $USE_GPUS $NVIDIA_ENV \
        --env="DISPLAY" \
        --env="QT_X11_NO_MITSHM=1" \
        --volume="/tmp/.X11-unix:/tmp/.X11-unix:rw" \
        --network host \
        $IMAGE_NAME bash -c "sleep 30"

    mkdir -p "$HOST_ROS2_WS_PATH"
    echo "Copiando workspace para o host..."
    docker cp temp_container:/root/ros2_ws/. "$HOST_ROS2_WS_PATH"
    docker rm -f temp_container
fi

echo "Iniciando container com ROS2 persistente..."

# --- Inicialização com as variáveis de rede corrigidas ---
docker run -it --rm --name $CONTAINER_NAME \
    $USE_GPUS \
    $NVIDIA_ENV \
    --env="DISPLAY" \
    --env="XAUTHORITY=/root/.Xauthority" \
    --env="QT_QPA_PLATFORM=xcb" \
    --env="QT_X11_NO_MITSHM=1" \
    --env="QT_OPENGL=desktop" \
    --env="LIBGL_ALWAYS_INDIRECT=0" \
    --env="GZ_PARTITION=imav_26" \
    --env="GZ_IP=127.0.0.1" \
    --env="ROS_DOMAIN_ID=0" \
    --env="XDG_RUNTIME_DIR=/tmp/runtime-root" \
    --volume="/tmp/.X11-unix:/tmp/.X11-unix:rw" \
    -v "$HOME/.Xauthority:/root/.Xauthority:ro" \
    -v "$HOME/.gz:/root/.gz" \
    --network host \
    --ipc=host \
    --pid=host \
    --privileged \
    --device /dev/dri \
    --device /dev/snd:/dev/snd \
    --device /dev/bus/usb \
    -v "$HOST_ROS2_WS_PATH/src:/root/ros2_ws/src" \
    $IMAGE_NAME \
    bash -c "
        mkdir -p /tmp/runtime-root && chmod 700 /tmp/runtime-root
        
        echo '=== Custom Setup Starting ==='
        
        # 1. Source the main ROS2 installation
        ROS_SETUP=\$(ls /opt/ros/*/setup.bash 2>/dev/null | head -n 1)
        if [ -n \"\$ROS_SETUP\" ]; then
            echo \"Sourcing system ROS 2 installation from \$ROS_SETUP...\"
            source \"\$ROS_SETUP\"
        else
            echo \"Warning: Could not find system ROS 2 installation in /opt/ros/\"
        fi

        cd /root/ros2_ws
        
        echo 'Running colcon build...'
        colcon build --symlink-install
        
        echo 'Exporting environment variables...'
        export RUN_TYPE='simulation'
        export ZENOH_CONFIG='/root/ros2_ws/zenoh_config.json'
        
        echo 'Sourcing workspace...'
        if [ -f 'install/setup.bash' ]; then
            source install/setup.bash
        fi
        
        echo '=== Custom Setup Complete! ==='
        
        # 2. Append runtime environment safely to .bashrc to preserve terminal colors
        echo '
if [ -n \"'$ROS_SETUP'\" ]; then source \"'$ROS_SETUP'\"; fi
if [ -f /root/ros2_ws/install/setup.bash ]; then source /root/ros2_ws/install/setup.bash; fi
export RUN_TYPE=simulation
export ZENOH_CONFIG=/root/ros2_ws/zenoh_config.json
' >> /root/.bashrc

        # 3. Open a normal interactive login shell
        exec bash --login
    "