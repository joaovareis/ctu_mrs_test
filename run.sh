#!/bin/bash

# Caminho para a raiz do projeto
PROJECT_ROOT=$(dirname "$(realpath "$0")")

# --- Carrega as variáveis do arquivo .env se ele existir ---
if [ -f "$PROJECT_ROOT/.env" ]; then
    export $(grep -v '^#' "$PROJECT_ROOT/.env" | xargs)
else
    echo "Aviso: Arquivo .env não encontrado!"
fi

# Nome da imagem Docker
IMAGE_NAME="imav_26"

# Nome do contêiner
CONTAINER_NAME="imav_26_container"

# Path para guardar o ros2_ws e o cache do rosdep no host
HOST_ROS2_WS_PATH="$PROJECT_ROOT/$CONTAINER_NAME/ros2_ws"
HOST_ROSDEP_CACHE_PATH="$PROJECT_ROOT/$CONTAINER_NAME/rosdep_cache"

echo "Configurando permissões do servidor X..."
xhost +local:root > /dev/null

# --- Detecção de GPU unificada ---
if [ -z "$(lspci | grep -i nvidia)" ]; then
    USE_GPUS=""
    NVIDIA_ENV=""
    echo "NVIDIA GPU NÃO detectada. Usando renderização padrão."
else
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

# Garante que a pasta de cache do rosdep existe no host para ser mapeada
mkdir -p "$HOST_ROSDEP_CACHE_PATH"

echo "Iniciando container com ROS2 persistente..."

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
    --env="GIT_USER_NAME=$GIT_USER_NAME" \
    --env="GIT_USER_EMAIL=$GIT_USER_EMAIL" \
    --env="GIT_TOKEN=$GIT_TOKEN" \
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
    -v "$HOST_ROSDEP_CACHE_PATH:/root/.ros/rosdep" \
    $IMAGE_NAME \
    bash -c "
        mkdir -p /tmp/runtime-root && chmod 700 /tmp/runtime-root
        
        echo '=== Custom Setup Starting ==='
        
        # 1. Configuração Automática do Git (HTTPS Privilegiado)
        if [ -n \"\$GIT_USER_NAME\" ] && [ -n \"\$GIT_USER_EMAIL\" ]; then
            echo 'Configurando identidade do Git...'
            git config --global user.name \"\$GIT_USER_NAME\"
            git config --global user.email \"\$GIT_USER_EMAIL\"
            
            if [ -n \"\$GIT_TOKEN\" ]; then
                echo 'Configurando credenciais do Token...'
                git config --global credential.helper store
                echo \"https://\$GIT_USER_NAME:\$GIT_TOKEN@github.com\" > /root/.git-credentials
                chmod 600 /root/.git-credentials
            fi
        fi

        # Neutraliza a interceptação do script 'shell_additions.sh' da CTU
        unset -f git
        
        # 2. Source do ROS2 estável
        ROS_SETUP=\$(ls /opt/ros/*/setup.bash 2>/dev/null | head -n 1)
        if [ -n \"\$ROS_SETUP\" ]; then
            echo \"Sourcing system ROS 2 installation from \$ROS_SETUP...\"
            source \"\$ROS_SETUP\"
        fi

        cd /root/ros2_ws
        
        # 3. Otimização do rosdep (Usa cache persistente do Host)
        if [ ! -d \"/root/.ros/rosdep/sources.cache\" ]; then
            echo 'Primeira inicialização: Atualizando fontes do rosdep...'
            rosdep update
        else
            echo 'Cache do rosdep detectado. Pulando atualização de fontes...'
        fi
        
        echo 'Verificando/instalando dependências locais com rosdep...'
        rosdep install --from-paths src --ignore-src -y --rosdistro jazzy 2>/dev/null || true
        
        echo 'Running colcon build...'
        colcon build --symlink-install
        
        echo 'Exporting environment variables for the main process...'
        export RUN_TYPE='simulation'
        export ZENOH_CONFIG='/root/ros2_ws/zenoh_config.json'
        export RMW_IMPLEMENTATION=rmw_zenoh_cpp
        export UAV_NAME=uav1
        export USE_SIM_TIME=\"true\"
        
        echo 'Sourcing workspace...'
        if [ -f 'install/setup.bash' ]; then
            source install/setup.bash
        fi
        
        echo '=== Custom Setup Complete! ==='
        
        # Limpa injeções antigas para evitar duplicidade no .bashrc
        sed -i '/# CONFIGURACOES_IMAV_DOCKER_EXEC/,/# FIM_CONFIGURACOES_IMAV_DOCKER_EXEC/d' /root/.bashrc

        # Insere as configurações limpas delimitadas por tags para o docker exec
        echo '
# CONFIGURACOES_IMAV_DOCKER_EXEC
if [ -n \"'$ROS_SETUP'\" ]; then source \"'$ROS_SETUP'\"; fi
if [ -f /root/ros2_ws/install/setup.bash ]; then source /root/ros2_ws/install/setup.bash; fi
unset -f git
export RUN_TYPE=simulation
export RMW_IMPLEMENTATION=rmw_zenoh_cpp
export UAV_NAME=uav1
export USE_SIM_TIME=\"true\"
export ZENOH_CONNECT=tcp/127.0.0.1:7447
unset ZENOH_CONFIG
# FIM_CONFIGURACOES_IMAV_DOCKER_EXEC
' >> /root/.bashrc

        exec bash --login
    "