cmake_minimum_required(VERSION 3.22)

project(i.in.svneo LANGUAGES NONE)

include(build_addon)

build_addon(
  ${PROJECT_NAME}
  SOURCES ${PROJECT_NAME}.py
  DOCFILES
    ${PROJECT_NAME}.html
    ${PROJECT_NAME}.md)

add_files_to_etc_dir(${PROJECT_NAME}
  FILES grass_optical_lib.py)