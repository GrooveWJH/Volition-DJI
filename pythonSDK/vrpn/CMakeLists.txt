cmake_minimum_required(VERSION 3.10)
project(VRPNClient)

set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include(FetchContent)
FetchContent_Declare(
    vrpn
    GIT_REPOSITORY https://github.com/vrpn/vrpn.git
    GIT_TAG master
)

set(VRPN_BUILD_CLIENT_LIBRARY ON CACHE BOOL "Build the VRPN client library" FORCE)

FetchContent_MakeAvailable(vrpn)

FetchContent_Declare(
    libzmq
    GIT_REPOSITORY https://github.com/zeromq/libzmq.git
    GIT_TAG master
)
FetchContent_Declare(
    cppzmq
    GIT_REPOSITORY https://github.com/zeromq/cppzmq.git
    GIT_TAG master
)

FetchContent_MakeAvailable(libzmq)
FetchContent_MakeAvailable(cppzmq)

# VRPN to ZeroMQ bridge (send)
add_executable(vrpn_send send.cpp)
target_include_directories(vrpn_send PRIVATE
    ${vrpn_SOURCE_DIR}
    ${cppzmq_SOURCE_DIR}
    ${libzmq_SOURCE_DIR}/include
)
target_link_libraries(vrpn_send PRIVATE vrpn libzmq)


# Create symbolic link for compile_commands.json (faster than copy)
if(CMAKE_EXPORT_COMPILE_COMMANDS AND NOT CMAKE_SOURCE_DIR STREQUAL CMAKE_BINARY_DIR)
    set(_compile_commands_src "${CMAKE_BINARY_DIR}/compile_commands.json")
    set(_compile_commands_dst "${CMAKE_SOURCE_DIR}/compile_commands.json")

    # Create symlink at configure time (only runs once)
    if(NOT EXISTS "${_compile_commands_dst}")
        execute_process(
            COMMAND ${CMAKE_COMMAND} -E create_symlink
                    "${_compile_commands_src}"
                    "${_compile_commands_dst}"
            WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
        )
        message(STATUS "Created symlink: compile_commands.json -> build/compile_commands.json")
    endif()
endif()