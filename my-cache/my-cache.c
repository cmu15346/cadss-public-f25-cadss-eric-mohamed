#include <cache.h>
#include <stdio.h>
#include <sys/types.h>
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
    uint64_t r; // the number of RRIP bits
    uint64_t **timestamps_or_rrip_values; // timestamps for LRU (if r = 0) or RRIP values (if r > 0)
    uint64_t **cache_matrix; // a matrix of valid bits and tags

    // victim cache 
    uint64_t i; // the number of entries in the victim cache
    uint64_t *victim_cache; // valid bits and tags for victim cache
    uint64_t *victim_timestamps; // timestamps for victim cache
} cache_def;

cache* self = NULL;
cache_def* main_cache = NULL;

coher* coherComp = NULL;

// Request queues
pendingRequest* readyReq = NULL;
pendingRequest* pendReq = NULL;

// true if using RRIP, false if using LRU
bool rrip = false;
// true if using victim cache, false otherwise
bool victim_cache = false;

int processorCount = 1;
int CADSS_VERBOSE = 1;
int countDown = 0;

void memoryRequest(trace_op* op, int processorNum, int64_t tag,
                   void (*callback)(int, int64_t));
void coherCallback(int type, int procNum, int64_t addr);
uint64_t get_max(uint64_t *A, uint64_t E);
uint64_t get_max_rrip(uint64_t *rrip_values, uint64_t E);
void modify_timestamps(uint64_t *timestamps_or_rrip_values, uint64_t E, uint64_t lineAccessed);

// Return victim index if tag found, else -1
static int64_t lookupVictim(uint64_t addressTag) {
    if (!victim_cache) return -1;
    for(uint64_t i = 0; i < main_cache->i; i++){
        uint64_t cache_line = main_cache->victim_cache[i];
        // if the valid bit is set to 1 and the tags match
        if((cache_line >> 63) && (((cache_line << 1) >> 1) == addressTag)){
            modify_timestamps(main_cache->victim_timestamps, main_cache->i, i);
            return (uint64_t)i;
        }
    }
    return -1;
}

void installVictimLine(uint64_t addr, uint64_t tag) {
    uint64_t lineIndex = 0;
    bool found_empty = false;

    for (uint64_t i = 0; i < main_cache->i; i++) {
        if (!(main_cache->victim_cache[i] >> 63)) { // invalid line found
            lineIndex = i;
            found_empty = true;
            break;
        }
    }

    // need to evict LRU line
    if (!found_empty) {
        lineIndex = get_max(main_cache->victim_timestamps, main_cache->i);
    }

    // install the new line
    main_cache->victim_cache[lineIndex] = (tag | ((uint64_t)1 << 63));

    modify_timestamps(main_cache->victim_timestamps, main_cache->i, lineIndex);
}


// Helper function to install a cache line
void installCacheLine(uint64_t addr, uint64_t setIndex, uint64_t tag) {
    // Find an empty line or evict LRU or RRIP line
    uint64_t lineIndex = 0;
    uint64_t evicted_line = 0;
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
        if(rrip){
            // Need to evict RRIP
            lineIndex = get_max_rrip(main_cache->timestamps_or_rrip_values[setIndex], main_cache->E);
        }
        else {
            // Need to evict LRU
            lineIndex = get_max(main_cache->timestamps_or_rrip_values[setIndex], main_cache->E);
        }
        evicted_line = main_cache->cache_matrix[setIndex][lineIndex];
    }
    
    // Install the new line
    if(rrip) {
        // Set valid bit to 1 and store the tag
        main_cache->cache_matrix[setIndex][lineIndex] = (tag | ((uint64_t)0x1 << 63));
        // Set RRIP value to 2^r - 2 on insertion
        main_cache->timestamps_or_rrip_values[setIndex][lineIndex] = (1 << main_cache->r) - 2;
    } 
    else {
        // Update timestamps for LRU
        main_cache->cache_matrix[setIndex][lineIndex] = (tag | ((uint64_t)0x1 << 63));
        modify_timestamps(main_cache->timestamps_or_rrip_values[setIndex], main_cache->E, lineIndex);
    }

    if (victim_cache && evicted_line != 0) {
        uint64_t evicted_tag = (evicted_line << 1) >> 1;
        installVictimLine(0, evicted_tag);
    }
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
    b: the number of block bits
    r: the number of RRIP bits
    RETURNS: an object of type cache */
void init_main_cache(uint64_t s, uint64_t E, uint64_t b, uint64_t i, uint64_t r){
    main_cache = (cache_def*)xcalloc(1, sizeof(cache_def));
    main_cache->s = (uint64_t)s;
    main_cache->E = (uint64_t)E;
    main_cache->b = (uint64_t)b;
    main_cache->i = (uint64_t)i;
    main_cache->r = (uint64_t)r;

    // initialize a 2d array with rows = number of sets and columns = number of 
    // lines that stores the timestamp of each line
    main_cache->timestamps_or_rrip_values = (uint64_t**)xcalloc((uint64_t)1 << main_cache->s, sizeof(uint64_t*));
    
    // initialize the matrix of tags (we do 1 << c->s because the number of
    // sets is 2^s)
    main_cache->cache_matrix = (uint64_t**)xcalloc((uint64_t)1 << main_cache->s, sizeof(uint64_t*));
    
    // initialize the victim cache if needed
    if(victim_cache){
        main_cache->victim_cache = (uint64_t*)xcalloc(main_cache->i, sizeof(uint64_t));
        main_cache->victim_timestamps = (uint64_t*)xcalloc(main_cache->i, sizeof(uint64_t));
    }

    // initialize each row of the tag matrix and timestamp matrix
    for(int i = 0; i < ((uint64_t)1 << main_cache->s); i++){
        main_cache->timestamps_or_rrip_values[i] = xcalloc(main_cache->E, sizeof(uint64_t));
        main_cache->cache_matrix[i] = xcalloc(main_cache->E, sizeof(uint64_t));
    }
}

/* set timestamps[lineAccessed] to 0 and increment the other lines
   ARGS: 
      A: the array nonAccessTimes 
      E: the number of lines
      lineAccessed: the index of the line we accessed
   RETURNS: N/A */
void modify_timestamps(uint64_t *timestamps_or_rrip_values, uint64_t E, uint64_t lineAccessed){
    timestamps_or_rrip_values[lineAccessed] = 0;
    for (uint64_t i = 0; i < lineAccessed; i++){
        timestamps_or_rrip_values[i] = timestamps_or_rrip_values[i] + 1;
    }
    for (uint64_t i = lineAccessed + 1; i < E; i++){
        timestamps_or_rrip_values[i] = timestamps_or_rrip_values[i] + 1;
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

/* get the index of the line to evict using RRIP
   ARGS: 
      rrip_values: the array of RRIP values
      E: the length of rrip_values
   RETURNS: the index of the line to evict */
uint64_t get_max_rrip(uint64_t *rrip_values, uint64_t E){
    uint64_t max_rrip = (1 << main_cache->r) - 1;
    while (true) {
        // Look for a line with RRIP value equal to max_rrip
        for (uint64_t i = 0; i < E; i++)
            if (rrip_values[i] == max_rrip) return i;
        // If none found, increment all RRIP values 
        for (uint64_t i = 0; i < E; i++) 
            // redundant?
            if (rrip_values[i] < max_rrip)
                rrip_values[i]++;
    }
}

cache* init(cache_sim_args* csa)
{
    int op;
    uint64_t E = 0, s = 0, b = 0, r = 0, i = 0;
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

            // entries in victim cache
            case 'i':
                victim_cache = true;
                i = atoi_safe(op, optarg);
                break;

            // bits in a RRIP-based replacement policy 
            case 'R':
                rrip = true;
                r = atoi_safe(op, optarg);
                break;
        }
    }

    init_main_cache(s, E, b, i, r);

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
    
    // Calculate block-aligned address by clearing the block offset bits
    uint64_t addr = (op->memAddress & ~((1ULL << main_cache->b) - 1));
    
    // extract the set index from the memory address
    uint64_t addressSetIndex = (addr >> main_cache->b) & (~((uint64_t)-1 << main_cache->s));
    // extract the tag bits from the memory address
    uint64_t addressTag = (addr >> (main_cache->b + main_cache->s));
    
    int hit_source = 0; // 0 = miss, 1 = main cache hit, 2 = victim cache hit
    uint64_t lineIndex = 0;

    // Check for main cache hit
    for(uint64_t i = 0; i < main_cache->E; i++){
        uint64_t cache_line = main_cache->cache_matrix[addressSetIndex][i];
        // if the valid bit is set to 1 and the tags match
        if((cache_line >> 63) && (((cache_line << 1) >> 1) == addressTag)){
            hit_source = 1;
            lineIndex = i;
            break;
        }
    }

    // Check for hit in victim cache, if not found in main cache
    int64_t victim_index = -1;
    if (!hit_source && victim_cache) {
        victim_index = lookupVictim(addressTag);
        if (victim_index != -1) {
            hit_source = 2;
        }
    }

    // Create pending request
    pendingRequest* pr = malloc(sizeof(pendingRequest));
    pr->tag = tag;
    pr->addr = addr;
    pr->memCallback = callback;
    pr->procNum = processorNum;
    pr->next = NULL;

    if (hit_source == 1) {
        // Main cache hit 
        if (rrip) {
            main_cache->timestamps_or_rrip_values[addressSetIndex][lineIndex] = 0;
        } else {
            modify_timestamps(main_cache->timestamps_or_rrip_values[addressSetIndex],
                              main_cache->E, lineIndex);
        }
        pr->next = readyReq;
        readyReq = pr;
        return;
    } 
    else if (hit_source == 2) {
        // Victim cache hit

        // Invalidate victim entry (since it will be moved to main cache)
        main_cache->victim_cache[victim_index] = 0;

        // Bring line into main cache
        installCacheLine(addr, addressSetIndex, addressTag);

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