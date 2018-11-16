set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR mips)

set(ROOTDIR /home/mikiya/workspace/sdk-master/out/rts3913l_evb)
set(CMAKE_SYSROOT "${ROOTDIR}/staging")
#set(CMAKE_STAGING_PREFIX ${ROOTDIR}/staging)

set(tools "${ROOTDIR}/host")
set(CMAKE_C_COMPILER "${tools}/bin/rsdk-linux-gcc")

set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)