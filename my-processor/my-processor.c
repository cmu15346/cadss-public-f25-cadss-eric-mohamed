#include <getopt.h>
#include <stdlib.h>
#include <stdio.h>
#include <sys/types.h>
#include <unistd.h>
#include "stdbool.h"

#include "processor.h"
#include "trace.h"
#include "cache.h"
#include "branch.h"

// Constants
#define MAX_REGS 32 // Since registers are between 0 and 31

trace_reader* tr = NULL;
cache* cs = NULL;
branch* bs = NULL;
processor* self = NULL;

int processorCount = 1;
int CADSS_VERBOSE = 0;

int* pendingMem = NULL;
int* pendingBranch = NULL;
int64_t* memOpTag = NULL;

typedef struct {
    bool ready; // True if the register holds a valid value
    int64_t tag; // Tag of the instruction that will produce the value (if not ready)
} reg_entry_t; // Register status table entry


typedef struct {
    trace_op *entries; // Array of instructions
    int head; // Index of the first valid entry
    int tail; // Index one past the last valid entry
    int count; // Number of valid entries
    int capacity; // Number of entries the queue can hold = d × (m×j + m×k)
} dispatch_queue_t; // Dispatch queue (FIFO)

typedef struct {
    bool busy; // True if the entry is in use
    int op_type; // Operation type: ALU / ALU_LONG / MEM / BRANCH
    int dest_reg; // Destination register (-1 if none)

    bool src1_ready, src2_ready; // True if the source operands are ready
    int val1, val2; // Operand values (if ready)
    int64_t tag1, tag2; // Tags of the instructions producing the operands (if not ready)

    int64_t tag; // Instruction tag for this entry (to allow CDB broadcasts)
} rs_entry_t; // Reservation station entry


typedef struct {
    bool busy; // True if the functional unit is in use
    int remaining; // Remaining cycles for the current operation to complete
    int64_t tag; // Tag of the instruction being processed
    int dest_reg; // Destination register
} func_unit_t; // Functional unit entry

typedef struct {
    bool busy; // True if the CDB is in use
    int64_t tag; // Tag of the instruction broadcasting
    int dest_reg; // Register to update
} cdb_t; // Common Data Bus entry

typedef struct {
    // Configuration parameters
    int fetch_rate;
    int dispatch_mult;
    int schedule_mult;
    int num_fast_alu;
    int num_long_alu;
    int num_cdb;

    reg_entry_t regs[MAX_REGS]; // Register status table
    dispatch_queue_t dq; // Dispatch queue

    rs_entry_t *rs_fast; // Reservation stations array for fast ALU FU (size = m*j)
    rs_entry_t *rs_long; // Reservation stations array for long ALU 1 FU (size = m*k)

    func_unit_t *fu_fast; // Number of fast ALU FUs
    func_unit_t *fu_long; // Number of long ALU FUs
    cdb_t *cdbs; // Common Data Buses

    int64_t tag_counter; // Counter to generate unique instruction tags
} processor_t;

processor_t *p = NULL;

// Dispatch queue operations
static bool dq_push(dispatch_queue_t *dq, const trace_op *op) {
    // Check for full queue
    if (dq->count >= dq->capacity)
        return false;
    // Add entry to the tail
    dq->entries[dq->tail] = *op;
    dq->tail = (dq->tail + 1) % dq->capacity;
    dq->count++;
    return true;
}

// Get the front entry of the dispatch queue without removing it
static trace_op* dq_front(dispatch_queue_t *dq) {
    return (dq->count == 0) ? NULL : &dq->entries[dq->head];
}

// Pop the front entry of the dispatch queue
static void dq_pop(dispatch_queue_t *dq) {
    if (dq->count == 0)
        return;
    dq->head = (dq->head + 1) % dq->capacity;
    dq->count--;
}

// Return reservation station capacities 
static inline int rs_cap_fast(void){ return p->schedule_mult * p->num_fast_alu; }
static inline int rs_cap_long(void){ return p->schedule_mult * p->num_long_alu; }

// Broadcast result on CDBs
static void broadcast(int64_t tag, int dest_reg) {
    // Loop over all fast ALU RS entries and update the ready status of all source operands
    // waiting for the instruction with the given tag to complete
    for (int i = 0; i < rs_cap_fast(); i++) {
        rs_entry_t *r = &p->rs_fast[i];
        if (r->busy) {
            if (!r->src1_ready && r->tag1 == tag) r->src1_ready = true;
            if (!r->src2_ready && r->tag2 == tag) r->src2_ready = true;
        }
    }

    // Loop over all long ALU RS entries and update the ready status of all source operands
    // waiting for the instruction with the given tag to complete
    for (int i = 0; i < rs_cap_long(); i++) {
        rs_entry_t *r = &p->rs_long[i];
        if (r->busy) {
            if (!r->src1_ready && r->tag1 == tag) r->src1_ready = true;
            if (!r->src2_ready && r->tag2 == tag) r->src2_ready = true;
        }
    }

    // Update the register file if the destination register matches
    if (dest_reg >= 0 && dest_reg < MAX_REGS && p->regs[dest_reg].tag == tag)
        p->regs[dest_reg].ready = true;
}

// Dispatch an instruction to the appropriate reservation station
static bool dispatch_to_rs(const trace_op *op) {
    // Determine which RS to use based on operation type
    rs_entry_t *rs = (op->op == ALU_LONG) ? p->rs_long : p->rs_fast;
    // Get the capacity of the chosen RS
    int cap = (op->op == ALU_LONG) ? rs_cap_long() : rs_cap_fast();

    // Find an empty RS entry and fill it with the instruction
    for (int i = 0; i < cap; i++) {
        if (!rs[i].busy) {
            rs_entry_t *r = &rs[i];
            r->busy = true;
            r->op_type = op->op;
            r->dest_reg = op->dest_reg;
            r->src1_ready = r->src2_ready = true;
            r->tag = p->tag_counter++;

            // Check source registers for readiness
            int s0 = op->src_reg[0], s1 = op->src_reg[1];

            // If source registers are not ready, set the tags accordingly
            if (s0 >= 0 && s0 < MAX_REGS && !p->regs[s0].ready) {
                r->src1_ready = false; r->tag1 = p->regs[s0].tag;
            }
            if (s1 >= 0 && s1 < MAX_REGS && !p->regs[s1].ready) {
                r->src2_ready = false; r->tag2 = p->regs[s1].tag;
            }

            // Update destination register status
            if (op->dest_reg >= 0 && op->dest_reg < MAX_REGS) {
                p->regs[op->dest_reg].ready = false;
                p->regs[op->dest_reg].tag = r->tag;
            }
            return true;
        }
    }
    return false;
}

// Issue ready instructions to functional units 
static int issue_ready(void) {
    int did = 0; // track progress
    // Issue ready instructions from fast ALU RS to fast ALU FUs
    for (int i = 0; i < rs_cap_fast(); i++) {
        rs_entry_t *r = &p->rs_fast[i];
        
        // If the instruction is ready, find an available functional unit
        if (r->busy && r->src1_ready && r->src2_ready) {
            for (int j = 0; j < p->num_fast_alu; j++) {
                func_unit_t *fu = &p->fu_fast[j];
                
                // If the functional unit is free, issue the instruction
                if (!fu->busy) {
                    fu->busy = true;
                    fu->remaining = 1; // fast ALU latency = 1
                    fu->tag = r->tag;
                    fu->dest_reg = r->dest_reg;
                    r->busy = false;
                    did = 1;
                    break;
                }
            }
        }
    }

    // Issue ready instructions from long ALU RS to long ALU FUs
    for (int i = 0; i < rs_cap_long(); i++) {
        rs_entry_t *r = &p->rs_long[i];

        // If the instruction is ready, find an available functional unit
        if (r->busy && r->src1_ready && r->src2_ready) {
            for (int j = 0; j < p->num_long_alu; j++) {
                func_unit_t *fu = &p->fu_long[j];

                // If the functional unit is free, issue the instruction
                if (!fu->busy) {
                    fu->busy = true;
                    fu->remaining = 3; // long ALU latency = 3
                    fu->tag = r->tag;
                    fu->dest_reg = r->dest_reg;
                    r->busy = false;
                    did = 1;
                    break;
                }
            }
        }
    }
    return did;
}

// Execute instructions in functional units and broadcast results when done
static int execute(void) {
    // Track remaining CDBs for this cycle
    int remaining_cdbs = p->num_cdb;
    int did = 0; // track progress

    // Execute fast ALU functional units
    for (int i = 0; i < p->num_fast_alu; i++) {
        func_unit_t *fu = &p->fu_fast[i];
        if (!fu->busy) continue;
        if (fu->remaining > 0) { fu->remaining--; did = 1; } // decrement remaining cycles
        if (fu->remaining == 0 && remaining_cdbs > 0) { // instruction complete
            broadcast(fu->tag, fu->dest_reg); // broadcast result
            fu->busy = false;
            remaining_cdbs--;
            did = 1;
        }
    }

    // Execute long ALU functional units
    for (int i = 0; i < p->num_long_alu; i++) {
        func_unit_t *fu = &p->fu_long[i];
        if (!fu->busy) continue; 
        if (fu->remaining > 0) { fu->remaining--; did = 1; } // decrement remaining cycles
        if (fu->remaining == 0 && remaining_cdbs > 0) { // instruction complete
            broadcast(fu->tag, fu->dest_reg); // broadcast result
            fu->busy = false;
            remaining_cdbs--; 
            did = 1;
        }
    }
    return did;
}

processor* init(processor_sim_args* psa)
{
    int op;

    tr = psa->tr;
    cs = psa->cache_sim;
    bs = psa->branch_sim;

    int fetch_rate = 1;
    int dispatch_mult = 1;
    int schedule_mult = 1;
    int num_fast_alu = 1;
    int num_long_alu = 1;
    int num_cdb = 1;

    while ((op = getopt(psa->arg_count, psa->arg_list, "f:d:m:j:k:c:")) != -1)
    {
        switch (op)
        {
            case 'f': fetch_rate = atoi(optarg); break;
            case 'd': dispatch_mult = atoi(optarg); break;
            case 'm': schedule_mult = atoi(optarg); break;
            case 'j': num_fast_alu = atoi(optarg); break;
            case 'k': num_long_alu = atoi(optarg); break;
            case 'c': num_cdb = atoi(optarg); break;
        }
    }

    pendingBranch = calloc(processorCount, sizeof(int));
    pendingMem = calloc(processorCount, sizeof(int));
    memOpTag = calloc(processorCount, sizeof(int64_t));

    self = calloc(1, sizeof(processor));

    // Initialize processor state
    p = calloc(1, sizeof(processor_t));


    // Set configuration parameters
    p->fetch_rate = fetch_rate;
    p->dispatch_mult = dispatch_mult;
    p->schedule_mult = schedule_mult;
    p->num_fast_alu = num_fast_alu;
    p->num_long_alu = num_long_alu;
    p->num_cdb = num_cdb;
    p->tag_counter = 1;

    // Initialize register status table
    for (int i = 0; i < MAX_REGS; i++){
        p->regs[i].ready = true;
        p->regs[i].tag = 0;
    }

    // Initialize dispatch queue
    p->dq.capacity = dispatch_mult * (schedule_mult * num_fast_alu + schedule_mult * num_long_alu);
    p->dq.entries = calloc(p->dq.capacity, sizeof(trace_op));
    p->dq.head = p->dq.tail = p->dq.count = 0;

    // Allocate reservation stations, functional units, and CDBs
    int rs_fast_count = schedule_mult * num_fast_alu;
    int rs_long_count = schedule_mult * num_long_alu;
    p->rs_fast = calloc(rs_fast_count, sizeof(rs_entry_t));
    p->rs_long = calloc(rs_long_count, sizeof(rs_entry_t));
    p->fu_fast = calloc(num_fast_alu, sizeof(func_unit_t));
    p->fu_long = calloc(num_long_alu, sizeof(func_unit_t));
    p->cdbs = calloc(num_cdb, sizeof(cdb_t));

    self->si.tick = tick;
    self->si.finish  = finish;
    self->si.destroy = destroy;
    return self;
}

const int64_t STALL_TIME = 100000;
int64_t tickCount = 0;
int64_t stallCount = -1;

int64_t makeTag(int procNum, int64_t baseTag)
{
    return ((int64_t)procNum) | (baseTag << 8);
}

void memOpCallback(int procNum, int64_t tag)
{
    int64_t baseTag = (tag >> 8);
    if (baseTag == memOpTag[procNum]) {
        memOpTag[procNum]++;
        pendingMem[procNum] = 0;
        stallCount = tickCount + STALL_TIME;
    }
}

int tick(void)
{
    trace_op* nextOp = NULL;

    bs->si.tick();
    cs->si.tick();
    tickCount++;

    if (tickCount == stallCount)
    {
        printf(
            "Processor may be stalled.  Now at tick - %ld, last op at %ld\n",
            tickCount, tickCount - STALL_TIME);
        for (int i = 0; i < processorCount; i++)
        {
            if (pendingMem[i] == 1)
            {
                printf("Processor %d is waiting on memory\n", i);
            }
        }
    }

    int progress = 0;

    // Tick the execute and issue stages
    progress = progress | execute();
    progress = progress | issue_ready();

    // Only dispatch up to dispatch_mult instructions
    int dispatched = 0;
    while (dispatched < p->dispatch_mult)
    {
        trace_op *front = dq_front(&p->dq);
        if (!front) break;
        if (dispatch_to_rs(front))
        {
            dq_pop(&p->dq);
            dispatched++;
            progress = 1;
        }
        else break;
    }

    for (int i = 0; i < processorCount; i++)
    {
        if (pendingMem[i] == 1 || pendingBranch[i] > 0)
        {
            if (pendingBranch[i] > 0) pendingBranch[i]--;
            progress = 1;
            continue;
        }

        // Only fetch up to fetch_rate instructions
        int fetched = 0;
        while (fetched < p->fetch_rate && p->dq.count < p->dq.capacity)
        {
            nextOp = tr->getNextOp(i);
            if (nextOp == NULL) break;
            progress = 1;

            switch (nextOp->op)
            {
                case MEM_LOAD:
                case MEM_STORE:
                    pendingMem[i] = 1;
                    cs->memoryRequest(nextOp, i, makeTag(i, memOpTag[i]), memOpCallback);
                    break;

                case BRANCH:
                    pendingBranch[i] =
                        (bs->branchRequest(nextOp, i) == nextOp->nextPCAddress) ? 0 : 1;
                    break;

                case ALU:
                case ALU_LONG:
                    dq_push(&p->dq, nextOp);
                    fetched++;
                    break;
            }
            free(nextOp);
        }
    }

    // Check if there is any progress made in this tick
    if (p->dq.count > 0) progress = 1;

    // Check reservation stations and functional units for busy entries
    for (int i = 0; i < rs_cap_fast(); i++)
        if (p->rs_fast[i].busy) { progress = 1; break; }

    for (int i = 0; i < rs_cap_long(); i++)
        if (p->rs_long[i].busy) { progress = 1; break; }

    for (int i = 0; i < p->num_fast_alu; i++)
        if (p->fu_fast[i].busy) { progress = 1; break; }

    for (int i = 0; i < p->num_long_alu; i++)
        if (p->fu_long[i].busy) { progress = 1; break; }

    return progress;
}


int finish(int outFd)
{
    int c = cs->si.finish(outFd);
    int b = bs->si.finish(outFd);
    char buf[32];
    size_t charCount = snprintf(buf, 32, "Ticks - %ld\n", tickCount);
    (void)!write(outFd, buf, charCount + 1);
    return (b || c) ? 1 : 0;
}

int destroy(void)
{
    int c = cs->si.destroy();
    int b = bs->si.destroy();

    if (p) {
        free(p->dq.entries);
        free(p->rs_fast);
        free(p->rs_long);
        free(p->fu_fast);
        free(p->fu_long);
        free(p->cdbs);
        free(p);
    }

    return (b || c) ? 1 : 0;
}
