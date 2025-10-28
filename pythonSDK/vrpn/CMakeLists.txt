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

add_executable(vrpn_client main.cpp)
target_include_directories(vrpn_client PRIVATE ${vrpn_SOURCE_DIR})

target_link_libraries(vrpn_client PRIVATE vrpn)

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

target_link_libraries(vrpn_client PRIVATE libzmq)

# VRPN to ZeroMQ bridge (send)
add_executable(vrpn_send send.cpp)
target_include_directories(vrpn_send PRIVATE
    ${vrpn_SOURCE_DIR}
    ${cppzmq_SOURCE_DIR}
    ${libzmq_SOURCE_DIR}/include
)
target_link_libraries(vrpn_send PRIVATE vrpn libzmq)


if(CMAKE_EXPORT_COMPILE_COMMANDS AND NOT CMAKE_SOURCE_DIR STREQUAL CMAKE_BINARY_DIR)
    set(_compile_commands_src "${CMAKE_BINARY_DIR}/compile_commands.json")
    set(_compile_commands_dst "${CMAKE_SOURCE_DIR}/compile_commands.json")
    add_custom_command(
        OUTPUT "${_compile_commands_dst}"
        COMMAND ${CMAKE_COMMAND} -E copy_if_different
                "${_compile_commands_src}"
                "${_compile_commands_dst}"
        DEPENDS "${_compile_commands_src}"
        COMMENT "Copy compile_commands.json next to the sources for clangd"
        VERBATIM
    )
    add_custom_target(update_compile_commands ALL
        DEPENDS "${_compile_commands_dst}"
    )
endif()
