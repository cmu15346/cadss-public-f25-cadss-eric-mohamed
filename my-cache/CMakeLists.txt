project(my-cache)
add_library(my-cache SHARED my-cache.c)
target_include_directories(my-cache PRIVATE ../common)
