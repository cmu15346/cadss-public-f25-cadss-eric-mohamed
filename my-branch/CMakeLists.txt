project(my-branch)
add_library(my-branch SHARED my-branch.c)
target_include_directories(my-branch PRIVATE ../common)
