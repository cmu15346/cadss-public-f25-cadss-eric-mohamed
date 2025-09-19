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
cache_def* main_cache = NULL;

coher* coherComp = NULL;

int processorCount = 1;
int CADSS_VERBOSE = 1;
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
void init_main_cache(uint64_t s, uint64_t E, uint64_t b){
    main_cache = (cache_def*)xcalloc(1, sizeof(cache_def));
    main_cache->s = (uint64_t)s;
    main_cache->E = (uint64_t)E;
    main_cache->b = (uint64_t)b;
    // initialize a 2d array with rows = number of sets and columns = number of 
    // lines that stores the timestamp of each line
    main_cache->timestamps = (uint64_t**)xcalloc((uint64_t)1 << main_cache->s, sizeof(uint64_t*));
    
    // initialize the matrix of tags (we do 1 << c->s because the number of
    // sets is 2^s)
    main_cache->cache_matrix = (uint64_t**)xcalloc((uint64_t)1 << main_cache->s, sizeof(uint64_t*));
    
    // initialize each row of the tag matrix and timestamp matrix
    for(int i = 0; i < ((uint64_t)1 << main_cache->s); i++){
        main_cache->timestamps[i] = xcalloc(main_cache->E, sizeof(uint64_t));
        main_cache->cache_matrix[i] = xcalloc(main_cache->E, sizeof(uint64_t));
    }
}

/* set timestamps[lineAccessed] to 0 and increment the other lines
   ARGS: 
      A: the array nonAccessTimes 
      E: the number of lines
      lineAccessed: the index of the line we accessed
   RETURNS: N/A */
void modify_timestamps(uint64_t *timestamps, uint64_t E, uint64_t lineAccessed){
    timestamps[lineAccessed] = 0;
    for (uint64_t i = 0; i < lineAccessed; i++){
        timestamps[i] = timestamps[i] + 1;
    }
    for (uint64_t i = lineAccessed + 1; i < E; i++){
        timestamps[i] = timestamps[i] + 1;
    }
}

/* get the index of the maximum element of A
   ARGS: 
      A: the array to find the maximum element of 
      E: the length of A
   RETURNS: the index of the maximum element of A */
uint64_t get_max(uint64_t *A, uint64_t E){
    uint64_t indexMax = 0;
    uint64_t max = A[0];
    for(uint64_t i = 1; i < E; i++){
        // if we find an element that is greater than our current max
        if(A[i] > max){
            indexMax = i;
            max = A[i];
        }
    }
    return indexMax;
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
                E = atoi_safe(op, optarg);
                break;
            }

            // Sets per cache
            case 's':
            {
                s = atoi_safe(op, optarg);
                break;
            }

            // block size in bits
            case 'b':
            {
                b = atoi_safe(op, optarg);
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

    init_main_cache(s, E, b);

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

    uint64_t memoryAddress = op->memAddress;

    // extract the set index from the memory address
    uint64_t addressSetIndex = (memoryAddress >> main_cache->b) & (~((uint64_t)-1 << main_cache->s));
    // extract the tag bits from the memory address
    uint64_t addressTag = (memoryAddress >> (main_cache->b + main_cache->s));
    
    bool found = false;
    bool eviction = false;
    uint64_t lineIndex = 0;

    // for every line in the set
    for(uint64_t i = 0; i < main_cache->E; i++){
        // get the cache line
        uint64_t cache_line = main_cache->cache_matrix[addressSetIndex][i];
        // if the valid bit is set to 0
        if(!(cache_line >> 63)){
            found = false;
            eviction = false;
            lineIndex = i;
            break;
        }
        // if the valid bit is set to 1 and the tags match
        if((cache_line >> 63) && (((cache_line << 1) >> 1) == addressTag)){
            found = true;
            eviction = false;
            lineIndex = i;
            break;
        }
        // if the valid bit is set to 1 and the tags don't match
        if((cache_line >> 63) && (((cache_line << 1) >> 1) != addressTag)){
            found = false;
            eviction = true;
            lineIndex = i;
            continue;
        }
    }

    // variable to keep track of the index to modify (lineIndex by default)
    uint64_t indexToModify = lineIndex;
    if(found){
        // printf("Cache hit for memory address with tag %ld\n", tag);
        callback(processorNum, tag);
    }
    else if(!found && !eviction){
        main_cache->cache_matrix[addressSetIndex][lineIndex] = (addressTag | ((uint64_t)0x1 << 63));
    }
    else if(!found && eviction){
        // the maxIndex would correspond to the LRU line
        uint64_t maxIndex = get_max(main_cache->timestamps[addressSetIndex], main_cache->E);
        indexToModify = maxIndex; 
        main_cache->cache_matrix[addressSetIndex][maxIndex] = (((uint64_t)0x1 << 63) | addressTag);
    }

    modify_timestamps(main_cache->timestamps[addressSetIndex], main_cache->E, indexToModify);

    // In a real cache simulator, the delay is based
    // on whether the request is a hit or miss.
    countDown = 2;

    // Tell memory about this request
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
