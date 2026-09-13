# ESP-IDF project: Tarea 1 CC5328 - simulated sensor DAQ over UART.
# Build:  idf.py build      Flash + serial monitor:  idf.py -p /dev/ttyUSB0 flash monitor
cmake_minimum_required(VERSION 3.22)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
# Only build the components "main" actually depends on (faster builds).
idf_build_set_property(MINIMAL_BUILD ON)
project(tarea1_daq)
