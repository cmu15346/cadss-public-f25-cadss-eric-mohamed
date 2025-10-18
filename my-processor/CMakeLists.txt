project(my-processor)
add_library(my-processor SHARED my-processor.c)
target_include_directories(my-processor PRIVATE ../common)
