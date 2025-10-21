#include <getopt.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

#include "processor.h"
#include "trace.h"
#include "cache.h"
#include "branch.h"

// --------------------- Data Structures and Global Variables ---------------------

// constants
#define MAX_REGS 33 // Since registers are between 0 and 32 (inclusive)

// some helper specs
int64_t makeTag(int procNum, int64_t baseTag);
void memOpCallback(int procNum, int64_t tag);
int compare_tags(const void* a, const void* b);

// parameters
int D = 1;  // dispatch queue multiplier [1,2]
int F = 1;  // fetch rate (instructions per cycle) [1,4]
int M = 1;  // schedule queue multiplier [1,2]
int J = 1;  // #fast ALUs [1,3]
int K = 1;  // #long ALUs [1,3]
int C = 1;  // #CDBs [1,4]

// struct pointers
trace_reader* tr = NULL; // trace reader
cache* cs = NULL; // cache
branch* bs = NULL; // branch predictor
processor* self = NULL; // processor instance

int processorCount = 1; // assuming single processor
int CADSS_VERBOSE = 0; // verbose flag

int* pendingMem = NULL; // pending memory operations
int* pendingBranch = NULL; // pending branch operations
int64_t* memOpTag = NULL; // memory operation tags

// instruciton struct
typedef struct {
    int valid;
    int tag;
    enum op_type op_type;
    int dest_reg;
    int src_reg[2];
    int src_ready[2];
    int src_tag[2];
    uint64_t pcAddress;
    uint64_t memAddress;
    
    // Pipeline stage tracking
    int fetch_cycle;
    int dispatch_cycle;
    int schedule_cycle;
    int execute_cycle;
    int state_update_cycle;
    
    // Execution tracking
    int fu_type;
    int cycles_left; // for execution
    int completed; // ready for SU
} instruction;

// FU struct
typedef struct {
    int busy;
    int tag;
    int cycles_left;
} function_unit;

// instruction queue struct
typedef struct {
    instruction* entries;
    int size;
    int count;
    int head;
    int tail;
} queue;

// states
queue dispatch_queue;
queue schedule_queue_type0;
queue schedule_queue_type1;
function_unit* fu_type0;
function_unit* fu_type1;

int* register_tags;  // each register's tag of instruction writing to it
int* register_ready; // 1 if register is ready, 0 if not

int64_t current_tag = 1;
int64_t current_cycle = -1;  // so first tick brings it to 0
int64_t total_instructions = 0;
int64_t instructions_fired = 0;
int fetch_done = 0;

const int64_t STALL_TIME = 100000;
int64_t tickCount = 0;
int64_t stallCount = -1;

// --------------------- Queue helper functions ---------------------
void queue_init(queue* q, int size) {
    q->entries = calloc(size, sizeof(instruction));
    q->size = size;
    q->count = 0;
    q->head = 0;
    q->tail = 0;
}

int queue_full(queue* q) {
    return q->count == q->size;
}

int queue_empty(queue* q) {
    return q->count == 0;
}

void queue_push(queue* q, instruction* inst) {
    if (queue_full(q)) return;
    q->entries[q->tail] = *inst;
    q->tail = (q->tail + 1) % q->size;
    q->count++;
}

instruction* queue_get(queue* q, int index) {
    if (index >= q->count) return NULL;
    int pos = (q->head + index) % q->size;
    return &q->entries[pos];
}

void queue_remove(queue* q, int index) {
    if (index >= q->count) return;
    
    for (int i = index; i < q->count - 1; i++) {
        int pos = (q->head + i) % q->size;
        int next_pos = (q->head + i + 1) % q->size;
        q->entries[pos] = q->entries[next_pos];
    }
    q->count--;
    q->tail = (q->tail - 1 + q->size) % q->size;
}

// --------------------- Processor simulator functions ---------------------

//
// init
//
//   Parse arguments and initialize the processor simulator components
//
processor* init(processor_sim_args* psa)
{
    int op;

    tr = psa->tr;
    cs = psa->cache_sim;
    bs = psa->branch_sim;

    // Parse command line arguments
    while ((op = getopt(psa->arg_count, psa->arg_list, "f:d:m:j:k:c:n:v")) != -1)
    {
        switch (op)
        {
            // fetch rate
            case 'f':
                F = atoi(optarg);
                break;

            // dispatch queue multiplier
            case 'd':
                D = atoi(optarg);
                break;

            // Schedule queue multiplier
            case 'm':
                M = atoi(optarg);
                break;

            // Number of fast ALUs
            case 'j':
                J = atoi(optarg);
                break;
            
            // Number of long ALUs
            case 'k':
                K = atoi(optarg);
                break;

            // Number of CDBs
            case 'c':
                C = atoi(optarg);
                break;

            // Verbosity
            case 'v':
                CADSS_VERBOSE = 1;
                break;
        }
    }

    // init SQs and DQ
    int dispatch_size = D * (M * J + M * K);
    queue_init(&dispatch_queue, dispatch_size);
    queue_init(&schedule_queue_type0, M * J);
    queue_init(&schedule_queue_type1, M * K);

    // init FUs
    fu_type0 = calloc(J, sizeof(function_unit));
    fu_type1 = calloc(K, sizeof(function_unit));

    // init registers
    register_tags = calloc(MAX_REGS, sizeof(int));
    register_ready = calloc(MAX_REGS, sizeof(int));
    for (int i = 0; i < MAX_REGS; i++) {
        register_ready[i] = 1;  // initially ready
    }

    // init pending arrays
    pendingBranch = calloc(processorCount, sizeof(int));
    pendingMem = calloc(processorCount, sizeof(int));
    memOpTag = calloc(processorCount, sizeof(int64_t));

    self = calloc(1, sizeof(processor));
    return self;
}

int64_t makeTag(int procNum, int64_t baseTag)
{
    return ((int64_t)procNum) | (baseTag << 8);
}

void memOpCallback(int procNum, int64_t tag)
{
    int64_t baseTag = (tag >> 8);

    // Is the completed memop one that is pending?
    if (baseTag == memOpTag[procNum])
    {
        memOpTag[procNum]++;
        pendingMem[procNum] = 0;
        stallCount = tickCount + STALL_TIME;
    }
    else
    {
        printf("memopTag: %ld != tag %ld\n", memOpTag[procNum], tag);
    }
}

// Comparison function for sorting by tag
int compare_tags(const void* a, const void* b) {
    int tag_a = *(const int*)a;
    int tag_b = *(const int*)b;
    return tag_a - tag_b;
}

void stage_state_update() {
    // collect completed but not yet state-updated instr.
    int completed_tags[100];
    int completed_count = 0;
    
    // check both SQs
    for (int i = 0; i < schedule_queue_type0.count; i++) {
        instruction* inst = queue_get(&schedule_queue_type0, i);
        if (inst->valid && inst->completed && inst->state_update_cycle == -1) {
            completed_tags[completed_count++] = inst->tag;
        }
    }

    for (int i = 0; i < schedule_queue_type1.count; i++) {
        instruction* inst = queue_get(&schedule_queue_type1, i);
        if (inst->valid && inst->completed && inst->state_update_cycle == -1) {
            completed_tags[completed_count++] = inst->tag;
        }
    }
    
    // lowest tag first
    qsort(completed_tags, completed_count, sizeof(int), compare_tags);
    
    // update no more than C (CDB limit)
    int updates = (completed_count < C) ? completed_count : C;
    
    // find and process each instr.
    for (int i = 0; i < updates; i++) {
        int tag = completed_tags[i];
        
        instruction* inst = NULL;
        
        // search instr. in both queues
        for (int j = 0; j < schedule_queue_type0.count; j++) {
            instruction* candidate = queue_get(&schedule_queue_type0, j);
            if (candidate->valid && candidate->tag == tag) {
                inst = candidate;
                break;
            }
        }

        if (!inst) {
            for (int j = 0; j < schedule_queue_type1.count; j++) {
                instruction* candidate = queue_get(&schedule_queue_type1, j);
                if (candidate->valid && candidate->tag == tag) {
                    inst = candidate;
                    break;
                }
            }
        }
        
        // tomasulo update
        if (inst) {
            inst->state_update_cycle = current_cycle;
            
            if (CADSS_VERBOSE) {
                printf("%d %d %d %d %d %d\n", 
                    inst->tag, 
                    inst->fetch_cycle,
                    inst->dispatch_cycle,
                    inst->schedule_cycle,
                    inst->execute_cycle,
                    inst->state_update_cycle);
            }
            
            // RF update
            if (inst->dest_reg >= 0 && inst->dest_reg < MAX_REGS) {
                if (register_tags[inst->dest_reg] == inst->tag) {
                    register_ready[inst->dest_reg] = 1;
                }
            }
            
            // update all waiting instr. in SQs
            for (int j = 0; j < schedule_queue_type0.count; j++) {
                instruction* waiting = queue_get(&schedule_queue_type0, j);
                if (waiting->valid) {
                    for (int k = 0; k < 2; k++) {
                        if (!waiting->src_ready[k] && waiting->src_tag[k] == tag) {
                            waiting->src_ready[k] = 1;
                        }
                    }
                }
            }
            
            for (int j = 0; j < schedule_queue_type1.count; j++) {
                instruction* waiting = queue_get(&schedule_queue_type1, j);
                if (waiting->valid) {
                    for (int k = 0; k < 2; k++) {
                        if (!waiting->src_ready[k] && waiting->src_tag[k] == tag) {
                            waiting->src_ready[k] = 1;
                        }
                    }
                }
            }
        }
    }
    
    // remove updated instructions from SQs
    for (int i = schedule_queue_type0.count - 1; i >= 0; i--) {
        instruction* inst = queue_get(&schedule_queue_type0, i);
        if (inst->valid && inst->state_update_cycle >= 0 && inst->state_update_cycle < current_cycle) {
            queue_remove(&schedule_queue_type0, i);
        }
    }
    
    for (int i = schedule_queue_type1.count - 1; i >= 0; i--) {
        instruction* inst = queue_get(&schedule_queue_type1, i);
        if (inst->valid && inst->state_update_cycle >= 0 && inst->state_update_cycle < current_cycle) {
            queue_remove(&schedule_queue_type1, i);
        }
    }
}


void stage_execute() {
    // update type 0 FUs (1 cycle latency)
    for (int i = 0; i < J; i++) {
        if (fu_type0[i].busy) {
            if (fu_type0[i].cycles_left > 0) {
                fu_type0[i].cycles_left--;
                if (fu_type0[i].cycles_left == 0) {
                    // Mark instruction as completed
                    int tag = fu_type0[i].tag;
                    for (int j = 0; j < schedule_queue_type0.count; j++) {
                        instruction* inst = queue_get(&schedule_queue_type0, j);
                        if (inst->valid && inst->tag == tag) {
                            inst->completed = 1;
                            break;
                        }
                    }
                    fu_type0[i].busy = 0;
                }
            }
        }
    }
    
    // update type 1 FUs (3 cycles latency)
    for (int i = 0; i < K; i++) {
        if (fu_type1[i].busy) {
            if (fu_type1[i].cycles_left > 0) {
                fu_type1[i].cycles_left--;
                if (fu_type1[i].cycles_left == 0) {
                    // Mark instruction as completed
                    int tag = fu_type1[i].tag;
                    for (int j = 0; j < schedule_queue_type1.count; j++) {
                        instruction* inst = queue_get(&schedule_queue_type1, j);
                        if (inst->valid && inst->tag == tag) {
                            inst->completed = 1;
                            break;
                        }
                    }
                    fu_type1[i].busy = 0;
                }
            }
        }
    }
}


void stage_schedule() {
    // collect ready instr. from both SQs
    int ready_tags[100];
    int ready_count = 0;

    // process type 0 first
    for (int i = 0; i < schedule_queue_type0.count; i++) {
        instruction* inst = queue_get(&schedule_queue_type0, i);
        if (inst->valid && !inst->completed && inst->cycles_left == -1 && 
            inst->dispatch_cycle + 1 < current_cycle) {
            if (inst->src_ready[0] && inst->src_ready[1]) {
                ready_tags[ready_count++] = inst->tag;
            }
        }
    }
    
    qsort(ready_tags, ready_count, sizeof(int), compare_tags);
    
    // fire type 0
    for (int i = 0; i < ready_count; i++) {
        // find available FU
        int fu_index = -1;
        for (int j = 0; j < J; j++) {
            if (!fu_type0[j].busy) {
                fu_index = j;
                break;
            }
        }
        
        if (fu_index == -1) break;
        
        // find instr.
        int tag = ready_tags[i];
        for (int j = 0; j < schedule_queue_type0.count; j++) {
            instruction* inst = queue_get(&schedule_queue_type0, j);
            if (inst->valid && inst->tag == tag && inst->cycles_left == -1) {
                inst->execute_cycle = current_cycle;
                inst->cycles_left = 1;  // type 0 has latency 1
                fu_type0[fu_index].busy = 1;
                fu_type0[fu_index].tag = tag;
                fu_type0[fu_index].cycles_left = 1;
                instructions_fired++;
                break;
            }
        }
    }
    
    // then process type 1
    ready_count = 0;
    for (int i = 0; i < schedule_queue_type1.count; i++) {
        instruction* inst = queue_get(&schedule_queue_type1, i);
        if (inst->valid && !inst->completed && inst->cycles_left == -1 && 
            inst->dispatch_cycle + 1 < current_cycle) {
            if (inst->src_ready[0] && inst->src_ready[1]) {
                ready_tags[ready_count++] = inst->tag;
            }
        }
    }
    
    qsort(ready_tags, ready_count, sizeof(int), compare_tags);
    
    // fire type 1
    for (int i = 0; i < ready_count; i++) {
        // find available FU
        int fu_index = -1;
        for (int j = 0; j < K; j++) {
            if (!fu_type1[j].busy) {
                fu_index = j;
                break;
            }
        }
        
        if (fu_index == -1) break;  // no available FU
        
        // find instr.
        int tag = ready_tags[i];
        for (int j = 0; j < schedule_queue_type1.count; j++) {
            instruction* inst = queue_get(&schedule_queue_type1, j);
            if (inst->valid && inst->tag == tag && inst->cycles_left == -1) {
                inst->execute_cycle = current_cycle;
                inst->cycles_left = 3;  // type 1 has latency 3
                fu_type1[fu_index].busy = 1;
                fu_type1[fu_index].tag = tag;
                fu_type1[fu_index].cycles_left = 3;
                instructions_fired++;
                break;
            }
        }
    }
}


void stage_dispatch() {
    for (int i = 0; i < dispatch_queue.count; ) {
        instruction* inst = queue_get(&dispatch_queue, i);

        // instr. should be valid
        if (!inst->valid) {
            i++;
            continue;
        }

        // instr. shouldn't be fetched already
        if (inst->fetch_cycle >= current_cycle) {
            i++;
            continue;
        }
        
        // which SQ it should go to?
        queue* target_queue = (inst->fu_type == 0) ? &schedule_queue_type0 : &schedule_queue_type1;
        
        // that SQ should have space
        if (queue_full(target_queue)) {
            i++;
            continue;
        }
        
        // dispatch this cycle, enter SQ next cycle
        inst->dispatch_cycle = current_cycle;
        inst->schedule_cycle = current_cycle + 1;
        
        // check sources are ready
        for (int j = 0; j < 2; j++) {
            int reg = inst->src_reg[j];
            if (reg >= 0 && reg < MAX_REGS) {
                if (register_ready[reg]) {
                    inst->src_ready[j] = 1;
                    inst->src_tag[j] = -1;
                } else {
                    inst->src_ready[j] = 0;
                    inst->src_tag[j] = register_tags[reg];
                }
            } else {
                inst->src_ready[j] = 1;  // no register needed
                inst->src_tag[j] = -1;
            }
        }
        
        // update destination register
        if (inst->dest_reg >= 0 && inst->dest_reg < MAX_REGS) {
            register_ready[inst->dest_reg] = 0;
            register_tags[inst->dest_reg] = inst->tag;
        }
        
        // move to SQ
        queue_push(target_queue, inst);
        queue_remove(&dispatch_queue, i);
    }
}

void stage_fetch() {
    if (fetch_done) return; // no more to fetch
    
    int fetched = 0;
    for (int i = 0; i < F && !queue_full(&dispatch_queue); i++) {
        trace_op* op = tr->getNextOp(0);
        if (op == NULL) {
            fetch_done = 1;
            break;
        }
        
        instruction inst;
        memset(&inst, 0, sizeof(instruction));
        inst.valid = 1;
        inst.tag = current_tag++;
        inst.op_type = op->op;
        inst.dest_reg = op->dest_reg;
        inst.src_reg[0] = op->src_reg[0];
        inst.src_reg[1] = op->src_reg[1];
        inst.pcAddress = op->pcAddress;
        inst.memAddress = op->memAddress;
        inst.fetch_cycle = current_cycle;
        inst.dispatch_cycle = -1;
        inst.schedule_cycle = -1;
        inst.execute_cycle = -1;
        inst.state_update_cycle = -1;
        inst.completed = 0;
        inst.cycles_left = -1;
        
        // determine FU type
        if (op->op == ALU || op->op == BRANCH || op->op == MEM_LOAD || op->op == MEM_STORE) {
            inst.fu_type = 0;
        } else if (op->op == ALU_LONG) {
            inst.fu_type = 1;
        } else {
            inst.fu_type = 0;  // Default
        }
        
        queue_push(&dispatch_queue, &inst);
        total_instructions++;
        fetched++;
        
        free(op);
    }
}

int tick(void)
{   
    // Pass along to the branch predictor and cache simulator that time ticked
    bs->si.tick();
    cs->si.tick();
    current_cycle++;
    
    // reverse order for timing to work
    stage_state_update();
    stage_execute();
    stage_schedule();
    stage_dispatch();
    stage_fetch();
    
    // check if simulation is done
    int progress = !fetch_done || 
                   !queue_empty(&dispatch_queue) || 
                   !queue_empty(&schedule_queue_type0) ||
                   !queue_empty(&schedule_queue_type1);
    
    return progress;
}


int finish(int outFd)
{
    // calculate and print stats
    double avg_fire_rate = (double)instructions_fired / (double)current_cycle;
    
    char buf[256];
    size_t charCount;

    charCount = snprintf(buf, 256, "# === Simulator Statistics ===\n");
    (void)!write(outFd, buf, charCount);
    
    charCount = snprintf(buf, 256, "# Average number of instructions fired per cycle: %.4f\n", avg_fire_rate);
    (void)!write(outFd, buf, charCount);
    
    charCount = snprintf(buf, 256, "# Total number of instructions: %ld\n", total_instructions);
    (void)!write(outFd, buf, charCount);
    
    charCount = snprintf(buf, 256, "# Total cycles: %ld\n", current_cycle);
    (void)!write(outFd, buf, charCount);
    
    charCount = snprintf(buf, 256, "Ticks - %ld\n", current_cycle);
    (void)!write(outFd, buf, charCount);
    
    // finish cache and branch sims
    int c = 0, b = 0;
    if (cs) c = cs->si.finish(outFd);
    if (bs) b = bs->si.finish(outFd);

    if (b || c)
        return 1;
    return 0;
}

int destroy(void)
{
    // clean up stuff
    if (dispatch_queue.entries) free(dispatch_queue.entries);
    if (schedule_queue_type0.entries) free(schedule_queue_type0.entries);
    if (schedule_queue_type1.entries) free(schedule_queue_type1.entries);
    
    if (fu_type0) free(fu_type0);
    if (fu_type1) free(fu_type1);
    
    if (register_tags) free(register_tags);
    if (register_ready) free(register_ready);
    
    if (pendingBranch) free(pendingBranch);
    if (pendingMem) free(pendingMem);
    if (memOpTag) free(memOpTag);
    
    int c = 0, b = 0;
    if (cs) c = cs->si.destroy();
    if (bs) b = bs->si.destroy();

    if (b || c)
        return 1;
    return 0;
}