cmake_minimum_required(VERSION 2.8)

project(tools)

#set(CMAKE_C_FLAGS "-g")
message(STATUS "root dir is ${CMAKE_SYSROOT}")

add_library(mstream SHARED stream_interface.c capture.c)
target_link_libraries(mstream rtstream rtsvideo)

add_executable(test_capture test.c)
target_link_libraries(test_capture mstream)
