#include <cache.h>
#include <stdio.h>
#include <trace.h>
#include <stdint.h>

#include <getopt.h>
#include <stdlib.h>
#include <assert.h>
#include <stdbool.h>

typedef struct _pendingRequest {
    int64_t tag;
    int8_t procNum;
    void (*memCallback)(int, int64_t);
} pendingRequest;

typedef struct cache_def {
    uint64_t s; // the number of set index bits 
    uint64_t E; // the number of lines in every set
    uint64_t b; // the number of block bits
    uint64_t **timestamps; // timpestamps for LRU 
    uint64_t **cache_matrix; // a matrix of valid bits and tags
} cache_def;

cache* self = NULL;
cache_def* cacheDef = NULL;

coher* coherComp = NULL;

int processorCount = 1;
int CADSS_VERBOSE = 0;
pendingRequest pending = {0};
int countDown = 0;

void memoryRequest(trace_op* op, int processorNum, int64_t tag,
                   void (*callback)(int, int64_t));
void coherCallback(int type, int procNum, int64_t addr);

/* Checks if the argument passed to the option opt is an integer argument 
   ARGS: 
      opt: the option the argument was passed to
      string: the argument
   RETURNS: atoi(string) if string is a valid integer */
uint64_t atoi_safe(int opt, char *string){
    int result = atoi(string);
    if (result == 0){
        fprintf(stderr, "Option -%c requires an integer argument.\n", opt);
        exit(0);
    }
    return result;
}

// THIS FUNCTION IS COPIED FROM A 15-122 FILE
/* xcalloc(nobj, size) returns a non-NULL pointer to
 * array of nobj objects, each of size size and
 * exits if the allocation fails.  Like calloc, the
 * array is initialized with zeroes.
 */
 static inline void* xcalloc(size_t nobj, size_t size) {
    void* p = calloc(nobj, size);
    if (p == NULL) {
      fprintf(stderr, "allocation failed\n");
      abort();
    }
    return p;
  }
  
/* initialzes an object of type cache with the data passed
    ARGS: 
    s: the number of set index bits
    E: the number of lines per set
    RETURNS: an object of type cache */
cache_def *init_cache_def(uint64_t s, uint64_t E, uint64_t b){
    cache_def *c = (cache_def*)xcalloc(1, sizeof(cache_def));
    c->s = (uint64_t)s;
    c->E = (uint64_t)E;
    c->b = (uint64_t)b;
    // initialize a 2d array with rows = number of sets and columns = number of 
    // lines that stores the timestamp of each line
    c->timestamps = (uint64_t**)xcalloc((uint64_t)1 << c->s, sizeof(uint64_t*));
    
    // initialize the matrix of tags (we do 1 << c->s because the number of
    // sets is 2^s)
    c->cache_matrix = (uint64_t**)xcalloc((uint64_t)1 << c->s, sizeof(uint64_t*));
    
    // initialize each row of the tag matrix and timestamp matrix
    for(int i = 0; i < ((uint64_t)1 << c->s); i++){
        c->cache_matrix[i] = xcalloc(c->E, sizeof(uint64_t));
        c->timestamps[i] = xcalloc(c->E, sizeof(uint64_t));
    }
    return c;
}

cache* init(cache_sim_args* csa)
{
    int op;
    uint64_t E = 0, s = 0, b = 0; // number of set index bits
    while ((op = getopt(csa->arg_count, csa->arg_list, "E:s:b:i:R:")) != -1)
    {
        switch (op)
        {
            // Lines per set
            case 'E':
            {
                uint64_t E = atoi_safe(op, optarg);
                break;
            }

            // Sets per cache
            case 's':
            {
                uint64_t s = atoi_safe(op, optarg);
                break;
            }

            // block size in bits
            case 'b':
            {
                uint64_t b = atoi_safe(op, optarg);
                break;
            }

            // entries in victim cache (to implement later)
            case 'i':
                break;

            // bits in a RRIP-based replacement policy (to implement later)
            case 'R':
                break;
        }
    }

    cache_def* cacheDef = init_cache_def(s, E, b);

    self = malloc(sizeof(cache));
    self->memoryRequest = memoryRequest;
    self->si.tick = tick;
    self->si.finish = finish;
    self->si.destroy = destroy;

    coherComp = csa->coherComp;
    coherComp->registerCacheInterface(coherCallback);

    return self;
}

// This routine is a linkage to the rest of the memory hierarchy
void coherCallback(int type, int procNum, int64_t addr)
{
    switch (type)
    {
        case NO_ACTION:
        case DATA_RECV:
            // TODO: check that the addr is the pending access
            // This indicates that the cache has received data from memory
            countDown = 1;
            break;

        case INVALIDATE:
            // This is taught later in the semester.
            break;

        default:
            break;
    }  
}

void memoryRequest(trace_op* op, int processorNum, int64_t tag,
                   void (*callback)(int, int64_t))
{
    assert(op != NULL);
    assert(callback != NULL);

    // Simple model to only have one outstanding memory operation
    if (countDown != 0)
    {
        assert(pending.memCallback != NULL);
        pending.memCallback(pending.procNum, pending.tag);
    }

    pending = (pendingRequest){
        .tag = tag, .procNum = processorNum, .memCallback = callback};

    // In a real cache simulator, the delay is based
    // on whether the request is a hit or miss.
    countDown = 2;
    
    // Tell memory about this request
    // TODO: only do this if this is a miss
    // TODO: evictions will also need a call to memory with
    //  invlReq(addr, procNum) -> true if waiting, false if proceed
    coherComp->permReq(false, op->memAddress, processorNum);
}

int tick()
{
    // Advance ticks in the coherence component.
    coherComp->si.tick();
    
    if (countDown == 1)
    {
        assert(pending.memCallback != NULL);
        pending.memCallback(pending.procNum, pending.tag);
    }

    return 1;
}

int finish(int outFd)
{
    return 0;
}

int destroy(void)
{
    // free any internally allocated memory here
    return 0;
}
