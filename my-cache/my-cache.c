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
    int64_t addr;
    int8_t procNum;
    void (*memCallback)(int, int64_t);
    struct _pendingRequest* next;
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

// Request queues
pendingRequest* readyReq = NULL;
pendingRequest* pendReq = NULL;

int processorCount = 1;
int CADSS_VERBOSE = 1;
int countDown = 0;

void memoryRequest(trace_op* op, int processorNum, int64_t tag,
                   void (*callback)(int, int64_t));
void coherCallback(int type, int procNum, int64_t addr);
uint64_t get_max(uint64_t *A, uint64_t E);
void modify_timestamps(uint64_t *timestamps, uint64_t E, uint64_t lineAccessed);

// Helper function to install a cache line
void installCacheLine(uint64_t addr, uint64_t setIndex, uint64_t tag) {
    // Find an empty line or evict LRU
    uint64_t lineIndex = 0;
    bool found_empty = false;
    
    for(uint64_t i = 0; i < main_cache->E; i++){
        uint64_t cache_line = main_cache->cache_matrix[setIndex][i];
        if(!(cache_line >> 63)){  // Invalid line found
            lineIndex = i;
            found_empty = true;
            break;
        }
    }
    
    if (!found_empty) {
        // Need to evict LRU
        lineIndex = get_max(main_cache->timestamps[setIndex], main_cache->E);
    }
    
    // Install the new line
    main_cache->cache_matrix[setIndex][lineIndex] = (tag | ((uint64_t)0x1 << 63));
    modify_timestamps(main_cache->timestamps[setIndex], main_cache->E, lineIndex);
}

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
            // No action needed
            break;

        case DATA_RECV:
            // Find the matching pending request and move it to ready
            if (pendReq != NULL && pendReq->addr == addr && pendReq->procNum == procNum) {
                pendingRequest* pr = pendReq;
                pendReq = pendReq->next;
                pr->next = readyReq;
                readyReq = pr;
            }
            else if (pendReq != NULL) {
                // Search through the list for matching request
                pendingRequest* prev = pendReq;
                pendingRequest* curr = pendReq->next;
                while (curr != NULL) {
                    if (curr->addr == addr && curr->procNum == procNum) {
                        prev->next = curr->next;
                        curr->next = readyReq;
                        readyReq = curr;
                        break;
                    }
                    prev = curr;
                    curr = curr->next;
                }
            }
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
    
    // Calculate block-aligned address
    uint64_t addr = (op->memAddress & ~((1ULL << main_cache->b) - 1));
    
    // extract the set index from the memory address
    uint64_t addressSetIndex = (addr >> main_cache->b) & (~((uint64_t)-1 << main_cache->s));
    // extract the tag bits from the memory address
    uint64_t addressTag = (addr >> (main_cache->b + main_cache->s));
    
    bool found = false;
    uint64_t lineIndex = 0;

    // Check for cache hit
    for(uint64_t i = 0; i < main_cache->E; i++){
        uint64_t cache_line = main_cache->cache_matrix[addressSetIndex][i];
        // if the valid bit is set to 1 and the tags match
        if((cache_line >> 63) && (((cache_line << 1) >> 1) == addressTag)){
            found = true;
            lineIndex = i;
            break;
        }
    }

    // Create pending request
    pendingRequest* pr = malloc(sizeof(pendingRequest));
    pr->tag = tag;
    pr->addr = addr;
    pr->memCallback = callback;
    pr->procNum = processorNum;
    pr->next = NULL;

    if(found){
        // Cache hit - update LRU and schedule callback for next tick
        modify_timestamps(main_cache->timestamps[addressSetIndex], main_cache->E, lineIndex);
        pr->next = readyReq;
        readyReq = pr;
        return;
    }

    // Cache miss - request permission from coherence system
    uint8_t perm = coherComp->permReq((op->op == MEM_LOAD), addr, processorNum);
    
    if (perm == 1) {
        // Permission granted immediately (higher-level cache hit)
        // Install the cache line and schedule callback
        installCacheLine(addr, addressSetIndex, addressTag);
        pr->next = readyReq;
        readyReq = pr;
    } else {
        // Permission denied - need to wait for data from memory
        pr->next = pendReq;
        pendReq = pr;
    }
}

int tick()
{
    // Advance ticks in the coherence component.
    coherComp->si.tick();
    
    // Process all ready requests
    pendingRequest* pr = readyReq;
    while (pr != NULL)
    {
        pendingRequest* next = pr->next;
        
        // When data arrives from coherence system for pending requests,
        // we need to install the cache line
        if (pr->addr != 0) {
            uint64_t setIndex = (pr->addr >> main_cache->b) & (~((uint64_t)-1 << main_cache->s));
            uint64_t tag = (pr->addr >> (main_cache->b + main_cache->s));
            installCacheLine(pr->addr, setIndex, tag);
        }
        
        // Call the processor callback
        pr->memCallback(pr->procNum, pr->tag);
        free(pr);
        pr = next;
    }
    readyReq = NULL;

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
