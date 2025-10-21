project(my-processor2)
add_library(my-processor2 SHARED my-processor2.c)
target_include_directories(my-processor2 PRIVATE ../common)
