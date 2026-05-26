# Escolha a imagem base
FROM ubuntu:24.04

# Definir variáveis de ambiente
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8 

ENV QT_X11_NO_MITSHM=1
ENV QT_QPA_PLATFORM=xcb
ENV LIBGL_ALWAYS_INDIRECT=0
ENV QT_OPENGL=desktop
ENV GZ_PARTITION=default
ENV GZ_TRANSPORT_IP=127.0.0.1

# ======================================================================
# Cria os arquivos do en_US.UTF-8 pro ROS
# ======================================================================
RUN apt-get update && apt-get upgrade -y && apt-get install -y \
    locales \
    sudo \
    curl \
    git \
    cmake \
    build-essential \
    software-properties-common \
    python3-pip \
    xxd \
    ninja-build \
    && locale-gen en_US en_US.UTF-8 \
    && update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

    
# ======================================================================
# Mesa utils
# ======================================================================

RUN apt-get update && apt-get install -y \
    mesa-utils \
    libgl1-mesa-dri \
    libglx0 \
    libgl1 \
    libegl1 \
    libgles2 \
    vulkan-tools \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ======================================================================
# ROS JAZZY
# ======================================================================
RUN add-apt-repository universe \
    && ROS_APT_SOURCE_VERSION=$(curl -s https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest | grep -F "tag_name" | awk -F'"' '{print $4}') \
    && curl -L -o /tmp/ros2-apt-source.deb "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${ROS_APT_SOURCE_VERSION}/ros2-apt-source_${ROS_APT_SOURCE_VERSION}.$(. /etc/os-release && echo ${UBUNTU_CODENAME:-${VERSION_CODENAME}})_all.deb" \
    && dpkg -i /tmp/ros2-apt-source.deb \
    && apt-get update && apt-get install -y \
    ros-dev-tools \
    ros-jazzy-desktop \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y \
    python3-empy=3.3.4-2 \
    && apt-mark hold python3-empy \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ======================================================================
# MRS CTU
# ======================================================================
RUN curl https://ctu-mrs.github.io/ppa2-stable/add_ppa.sh | bash \
    && apt-get update && apt-get install -y \
    ros-jazzy-mrs-uav-core\
    ros-jazzy-mrs-uav-gazebo-simulator \
    ros-jazzy-mrs-uav-px4-api \
    python3-colcon-mixin \
    python3-colcon-override-check \
    ros-jazzy-ament-cmake-clang-format \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ======================================================================
# Micro-XRCE-DDS-Agent
# ======================================================================
RUN git clone --recurse-submodules https://github.com/eProsima/Micro-XRCE-DDS-Agent.git /tmp/Micro-XRCE-DDS-Agent \
    && cd /tmp/Micro-XRCE-DDS-Agent \
    && mkdir build && cd build \
    && cmake -DTHIRDPARTY=ON .. \
    && make -j$(nproc) \
    && make install \
    && ldconfig \
    && rm -rf /tmp/Micro-XRCE-DDS-Agent
# ======================================================================
# PX4-Autopilot
# ======================================================================
RUN git clone --recursive https://github.com/PX4/PX4-Autopilot.git /root/PX4-Autopilot \
    && cd /root/PX4-Autopilot \
    && bash ./Tools/setup/ubuntu.sh --no-nuttx

# ======================================================================
# Setup do Workspace
# ======================================================================

RUN mkdir -p /root/ros2_ws/src
WORKDIR /root/ros2_ws

RUN git clone https://github.com/PX4/px4_msgs.git /root/ros2_ws/src/px4_msgs

# ======================================================================
# Bibliotecas principais
# ======================================================================

RUN apt-get update && apt-get install -y \
    python3-opencv \
    python3-pyzbar \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir --break-system-packages \
    colorful \
    git+https://github.com/cottsay/colcon-ansi-colors-example

# ======================================================================
# Setup dos mixins
# ======================================================================

RUN colcon mixin add default https://raw.githubusercontent.com/colcon/colcon-mixin-repository/master/index.yaml \
    && colcon mixin add mrs https://raw.githubusercontent.com/ctu-mrs/colcon_mixin/refs/heads/master/index.yaml \
    && colcon mixin update

RUN git clone -b ros2 https://github.com/ctu-mrs/mrs_uav_development.git /root/mrs_uav_development

# ======================================================================
# Clonar o repositorio da IMAV
# ======================================================================

ARG GIT_USER_EMAIL
ARG GIT_USER_NAME
ARG GITHUB_TOKEN

RUN git config --global user.email "$GIT_USER_EMAIL" \
    && git config --global user.name "$GIT_USER_NAME"

# ======================================================================
# Compila o workspace
# ======================================================================

RUN rosdep update \
    && /bin/bash -c "source /opt/ros/jazzy/setup.bash; \
                     rosdep install --from-paths src --ignore-src -y --rosdistro jazzy" \
    && rm -rf /var/lib/apt/lists/*

RUN /bin/bash -c "source /opt/ros/jazzy/setup.bash; \
                  colcon --output-style catkin_tools build --symlink-install"

RUN echo "source /opt/ros/jazzy/setup.bash" >> /root/.bashrc \
    && echo "source /root/mrs_uav_development/shell_additions/shell_additions.sh" >> /root/.bashrc \
    && echo "source /root/ros2_ws/install/local_setup.bash" >> /root/.bashrc \
    && echo "export COLCON_DEFAULT_OUTPUT_STYLE=catkin_tools" >> /root/.bashrc

# Comando padrão
WORKDIR /root/ros2_ws
CMD ["/bin/bash"]
