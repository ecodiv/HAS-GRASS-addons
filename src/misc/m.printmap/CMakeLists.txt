cmake_minimum_required(VERSION 3.22)

project(m.printmap LANGUAGES NONE)

include(build_addon)

build_addon(
  ${PROJECT_NAME}
  SOURCES ${PROJECT_NAME}.py
  DOCFILES
    m_printmap_01.png
    m_printmap_02.png
    m_printmap_03.png
    m_printmap_04.png
    ${PROJECT_NAME}.html
    ${PROJECT_NAME}.md)
