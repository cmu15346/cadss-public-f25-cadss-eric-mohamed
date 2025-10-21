#include <getopt.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

#include "processor.h"
#include "trace.h"
#include "cache.h"
#include "branch.h"

// Forward declarations for comparison function
int compare_tags(const void* a, const void* b);

// Pipeline parameters
int F = 1;  // Fetch rate
int D = 1;  // Dispatch queue multiplier
int M = 1;  // Schedule queue multiplier
int J = 1;  // Number of fast ALUs
int K = 1;  // Number of long ALUs
int C = 1;  // Number of CDBs

// Component pointers
trace_reader* tr = NULL;
cache* cs = NULL;
branch* bs = NULL;
processor* self = NULL;

int processorCount = 1;
int CADSS_VERBOSE = 0;

int* pendingMem = NULL;
int* pendingBranch = NULL;
int64_t* memOpTag = NULL;

// Instruction structure
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
    int fu_type;        // 0 or 1
    int cycles_left;    // For execution
    int completed;      // Ready for state update
} instruction;

// Queue structures
typedef struct {
    instruction* entries;
    int size;
    int count;
    int head;
    int tail;
} queue;

// Function unit structure
typedef struct {
    int busy;
    int tag;
    int cycles_left;
} function_unit;

// Global state
queue dispatch_queue;
queue schedule_queue_type0;
queue schedule_queue_type1;
function_unit* fu_type0;
function_unit* fu_type1;

int* register_tags;  // Tag of instruction writing to each register
int* register_ready; // Is register ready?

int64_t current_tag = 1;
int64_t current_cycle = -1;  // Start at -1 so first tick brings it to 0
int64_t total_instructions = 0;
int64_t instructions_fired = 0;
int fetch_done = 0;

// Queue helper functions
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
    
    // Shift all elements after index forward
    for (int i = index; i < q->count - 1; i++) {
        int pos = (q->head + i) % q->size;
        int next_pos = (q->head + i + 1) % q->size;
        q->entries[pos] = q->entries[next_pos];
    }
    q->count--;
    q->tail = (q->tail - 1 + q->size) % q->size;
}

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
            case 'f':  // fetch rate
                F = atoi(optarg);
                break;
            case 'd':  // dispatch queue multiplier
                D = atoi(optarg);
                break;
            case 'm':  // schedule queue multiplier
                M = atoi(optarg);
                break;
            case 'j':  // number of fast ALUs
                J = atoi(optarg);
                break;
            case 'k':  // number of long ALUs
                K = atoi(optarg);
                break;
            case 'c':  // number of CDBs
                C = atoi(optarg);
                break;
            case 'v':  // verbose
                CADSS_VERBOSE = 1;
                break;
        }
    }

    // Initialize queues
    int dispatch_size = D * (M * J + M * K);
    queue_init(&dispatch_queue, dispatch_size);
    queue_init(&schedule_queue_type0, M * J);
    queue_init(&schedule_queue_type1, M * K);

    // Initialize function units
    fu_type0 = calloc(J, sizeof(function_unit));
    fu_type1 = calloc(K, sizeof(function_unit));

    // Initialize register file
    register_tags = calloc(33, sizeof(int));
    register_ready = calloc(33, sizeof(int));
    for (int i = 0; i < 33; i++) {
        register_ready[i] = 1;  // All registers initially ready
    }

    pendingBranch = calloc(processorCount, sizeof(int));
    pendingMem = calloc(processorCount, sizeof(int));
    memOpTag = calloc(processorCount, sizeof(int64_t));

    self = calloc(1, sizeof(processor));
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

// Stage 5: State Update
void stage_state_update() {
    // Collect all completed instructions that haven't been state-updated yet
    int completed_tags[100];
    int completed_count = 0;
    
    // Check schedule queue type 0
    for (int i = 0; i < schedule_queue_type0.count; i++) {
        instruction* inst = queue_get(&schedule_queue_type0, i);
        if (inst->valid && inst->completed && inst->state_update_cycle == -1) {
            completed_tags[completed_count++] = inst->tag;
        }
    }
    
    // Check schedule queue type 1
    for (int i = 0; i < schedule_queue_type1.count; i++) {
        instruction* inst = queue_get(&schedule_queue_type1, i);
        if (inst->valid && inst->completed && inst->state_update_cycle == -1) {
            completed_tags[completed_count++] = inst->tag;
        }
    }
    
    // Sort by tag order (lowest first)
    qsort(completed_tags, completed_count, sizeof(int), compare_tags);
    
    // Process up to C instructions (CDB limit)
    int updates = (completed_count < C) ? completed_count : C;
    
    for (int i = 0; i < updates; i++) {
        int tag = completed_tags[i];
        
        // Find and process this instruction
        instruction* inst = NULL;
        
        // Search in type 0 queue
        for (int j = 0; j < schedule_queue_type0.count; j++) {
            instruction* candidate = queue_get(&schedule_queue_type0, j);
            if (candidate->valid && candidate->tag == tag) {
                inst = candidate;
                break;
            }
        }
        
        // Search in type 1 queue if not found
        if (!inst) {
            for (int j = 0; j < schedule_queue_type1.count; j++) {
                instruction* candidate = queue_get(&schedule_queue_type1, j);
                if (candidate->valid && candidate->tag == tag) {
                    inst = candidate;
                    break;
                }
            }
        }
        
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
            
            // Update register file
            if (inst->dest_reg >= 0 && inst->dest_reg < 33) {
                if (register_tags[inst->dest_reg] == inst->tag) {
                    register_ready[inst->dest_reg] = 1;
                }
            }
            
            // Update all waiting instructions in schedule queues
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
    
    // Now remove all instructions that have been state-updated from schedule queues
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

// Stage 4: Execute
void stage_execute() {
    // Update function units (type 0)
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
    
    // Update function units (type 1) - pipelined with 3 stages
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

// Stage 3: Schedule (Fire instructions)
void stage_schedule() {
    // Collect ready instructions from both queues
    int ready_tags[100];
    int ready_count = 0;
    
    // Check type 0 queue
    for (int i = 0; i < schedule_queue_type0.count; i++) {
        instruction* inst = queue_get(&schedule_queue_type0, i);
        // Instruction must spend at least one full cycle in schedule queue
        // If dispatched in cycle J, in schedule queue during cycle J+1, can fire in cycle J+2
        if (inst->valid && !inst->completed && inst->cycles_left == -1 && 
            inst->dispatch_cycle + 1 < current_cycle) {
            // Check if operands are ready
            if (inst->src_ready[0] && inst->src_ready[1]) {
                ready_tags[ready_count++] = inst->tag;
            }
        }
    }
    
    // Sort by tag (lowest first)
    qsort(ready_tags, ready_count, sizeof(int), compare_tags);
    
    // Fire type 0 instructions
    for (int i = 0; i < ready_count; i++) {
        // Find available FU
        int fu_index = -1;
        for (int j = 0; j < J; j++) {
            if (!fu_type0[j].busy) {
                fu_index = j;
                break;
            }
        }
        
        if (fu_index == -1) break;  // No available FU
        
        // Find instruction
        int tag = ready_tags[i];
        for (int j = 0; j < schedule_queue_type0.count; j++) {
            instruction* inst = queue_get(&schedule_queue_type0, j);
            if (inst->valid && inst->tag == tag && inst->cycles_left == -1) {
                // Fire instruction - execute cycle is when it fires
                inst->execute_cycle = current_cycle;
                inst->cycles_left = 1;  // Type 0 has latency 1
                fu_type0[fu_index].busy = 1;
                fu_type0[fu_index].tag = tag;
                fu_type0[fu_index].cycles_left = 1;
                instructions_fired++;
                break;
            }
        }
    }
    
    // Check type 1 queue
    ready_count = 0;
    for (int i = 0; i < schedule_queue_type1.count; i++) {
        instruction* inst = queue_get(&schedule_queue_type1, i);
        // Instruction must spend at least one full cycle in schedule queue
        // If dispatched in cycle J, in schedule queue during cycle J+1, can fire in cycle J+2
        if (inst->valid && !inst->completed && inst->cycles_left == -1 && 
            inst->dispatch_cycle + 1 < current_cycle) {
            // Check if operands are ready
            if (inst->src_ready[0] && inst->src_ready[1]) {
                ready_tags[ready_count++] = inst->tag;
            }
        }
    }
    
    // Sort by tag (lowest first)
    qsort(ready_tags, ready_count, sizeof(int), compare_tags);
    
    // Fire type 1 instructions
    for (int i = 0; i < ready_count; i++) {
        // Find available FU
        int fu_index = -1;
        for (int j = 0; j < K; j++) {
            if (!fu_type1[j].busy) {
                fu_index = j;
                break;
            }
        }
        
        if (fu_index == -1) break;  // No available FU
        
        // Find instruction
        int tag = ready_tags[i];
        for (int j = 0; j < schedule_queue_type1.count; j++) {
            instruction* inst = queue_get(&schedule_queue_type1, j);
            if (inst->valid && inst->tag == tag && inst->cycles_left == -1) {
                // Fire instruction - execute cycle is when it fires
                inst->execute_cycle = current_cycle;
                inst->cycles_left = 3;  // Type 1 has latency 3
                fu_type1[fu_index].busy = 1;
                fu_type1[fu_index].tag = tag;
                fu_type1[fu_index].cycles_left = 3;
                instructions_fired++;
                break;
            }
        }
    }
}

// Stage 2: Dispatch
void stage_dispatch() {
    // Scan dispatch queue from head to tail
    for (int i = 0; i < dispatch_queue.count; ) {
        instruction* inst = queue_get(&dispatch_queue, i);
        if (!inst->valid) {
            i++;
            continue;
        }
        
        // Instruction must have spent at least 1 cycle in dispatch queue
        // If fetched in cycle J, can dispatch in cycle J+1
        if (inst->fetch_cycle >= current_cycle) {
            i++;
            continue;
        }
        
        // Determine target schedule queue
        queue* target_queue = (inst->fu_type == 0) ? &schedule_queue_type0 : &schedule_queue_type1;
        
        // Check if schedule queue has space
        if (queue_full(target_queue)) {
            i++;
            continue;
        }
        
        // Dispatch instruction
        inst->dispatch_cycle = current_cycle;
        // Schedule cycle is when it enters the schedule queue (next cycle)
        inst->schedule_cycle = current_cycle + 1;
        
        // Check source operands
        for (int j = 0; j < 2; j++) {
            int reg = inst->src_reg[j];
            if (reg >= 0 && reg < 33) {
                if (register_ready[reg]) {
                    inst->src_ready[j] = 1;
                    inst->src_tag[j] = -1;
                } else {
                    inst->src_ready[j] = 0;
                    inst->src_tag[j] = register_tags[reg];
                }
            } else {
                inst->src_ready[j] = 1;  // No register needed
                inst->src_tag[j] = -1;
            }
        }
        
        // Update destination register
        if (inst->dest_reg >= 0 && inst->dest_reg < 33) {
            register_ready[inst->dest_reg] = 0;
            register_tags[inst->dest_reg] = inst->tag;
        }
        
        // Move to schedule queue
        queue_push(target_queue, inst);
        queue_remove(&dispatch_queue, i);
        // Don't increment i since we removed an element
    }
}

// Stage 1: Fetch/Decode
void stage_fetch() {
    if (fetch_done) return;
    
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
        
        // Determine function unit type
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
    current_cycle++;
    
    // Pass along to the branch predictor and cache simulator that time ticked
    if (bs) bs->si.tick();
    if (cs) cs->si.tick();
    
    // Process pipeline stages - order matters for correct timing
    // Based on spec: stages are processed to simulate latching behavior
    
    // Update function units (decrement counters, mark completed)
    stage_execute();
    
    // FIRST HALF OF CYCLE:
    // Fire ready instructions from schedule queues (before CDB broadcast)
    stage_schedule();
    
    // Dispatch instructions from dispatch queue to schedule queues
    stage_dispatch();
    
    // SECOND HALF OF CYCLE:
    // State update: write register file, broadcast on CDB to wake up instructions, remove completed
    stage_state_update();
    
    // Fetch new instructions into dispatch queue
    stage_fetch();
    
    // Check if simulation is done
    int progress = !fetch_done || 
                   !queue_empty(&dispatch_queue) || 
                   !queue_empty(&schedule_queue_type0) ||
                   !queue_empty(&schedule_queue_type1);
    
    return progress;
}


int finish(int outFd)
{
    // Calculate statistics
    double avg_fire_rate = (double)instructions_fired / (double)current_cycle;
    
    char buf[256];
    size_t charCount;
    
    // Output statistics
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
    
    int c = 0, b = 0;
    if (cs) c = cs->si.finish(outFd);
    if (bs) b = bs->si.finish(outFd);

    if (b || c)
        return 1;
    return 0;
}

int destroy(void)
{
    // Free queue entries
    if (dispatch_queue.entries) free(dispatch_queue.entries);
    if (schedule_queue_type0.entries) free(schedule_queue_type0.entries);
    if (schedule_queue_type1.entries) free(schedule_queue_type1.entries);
    
    // Free function units
    if (fu_type0) free(fu_type0);
    if (fu_type1) free(fu_type1);
    
    // Free register arrays
    if (register_tags) free(register_tags);
    if (register_ready) free(register_ready);
    
    // Free other arrays
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
