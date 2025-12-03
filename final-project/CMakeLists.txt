project(final-project)
add_library(final-project SHARED final-project.c)
target_include_directories(final-project PRIVATE ../common)
