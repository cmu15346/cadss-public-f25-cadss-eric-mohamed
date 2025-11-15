project(my-coherence)
add_library(my-coherence SHARED coherence.c protocol.c stree.c)
target_include_directories(coherence PRIVATE ../common)
