cmake_minimum_required(VERSION 3.20.0)
project(mrs_gazebo_custom_drone_example)

set(DEPENDENCIES
  ament_cmake
  ros_gz
)

foreach(DEP IN LISTS DEPENDENCIES)
  find_package(${DEP} REQUIRED)
endforeach()

## --------------------------------------------------------------
## |                           Install                          |
## --------------------------------------------------------------

install(DIRECTORY models/
  DESTINATION share/${PROJECT_NAME}/models
)

ament_package()
