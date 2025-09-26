#include <branch.h>
#include <trace.h>

#include <getopt.h>
#include <stdlib.h>
#include <assert.h>
#include <stdio.h>

typedef struct branch_def {
    // Simulation parameters
    uint64_t p; // number of processors
    uint64_t s; // predictor size
    uint64_t b; // BHR size
    uint64_t g; // predictor model

    // Predictor state
    uint8_t* counters;    // 2-bit saturating counters
    uint64_t* btb;        // Branch Target Buffer
    uint64_t bhr;         // Global Branch History Register
    
    // Derived values
    uint64_t predictor_size;  // 1 << s
    uint64_t index_mask;      // (1 << s) - 1
    uint64_t bhr_mask;        // (1 << b) - 1
} branch_def;

branch* self = NULL;
branch_def* branchSim = NULL;

// Function declarations
uint64_t branchRequest(trace_op* op, int processorNum);
int tick();
int finish(int outFd);
int destroy(void);

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

// Get predictor index based on PC and model type
uint64_t get_predictor_index(uint64_t pc, uint64_t bhr, uint64_t model, uint64_t s, uint64_t b) {
    uint64_t index_mask = (1ULL << s) - 1; // mask for s bits
    uint64_t pc_index = (pc >> 3) & index_mask;  // ignore lower 3 bits (word aligned)
    
    switch(model) {
        case 0: // 2-bit counters
            return pc_index;
        case 1: // GSHARE: XOR with BHR
            return (pc_index ^ bhr) & index_mask;
        case 2: // GSELECT: concatenate PC bits with BHR
            if (b >= s) return pc_index; // Fallback if b >= s, this shouldn't happen
            else
            {
                uint64_t pc_bits = (s - b);
                uint64_t pc_mask = (1ULL << pc_bits) - 1;
                return ((pc_index & pc_mask) | ((bhr & ((1ULL << b) - 1)) << pc_bits)) & index_mask;
            }
        case 3: // Yeh-Patt (not implemented)
            raise (SIGABRT);
            exit(-1);
        default: // Default to 2-bit counters
            return pc_index;
    }
}

void init_branchSim(uint64_t p, uint64_t s, uint64_t b, uint64_t g)
{
    branchSim = malloc(sizeof(branch_def));
    branchSim->p = p;
    branchSim->s = s;
    branchSim->b = b;
    branchSim->g = g;
    
    // Calculate derived values
    branchSim->predictor_size = 1ULL << s;
    branchSim->index_mask = branchSim->predictor_size - 1;
    branchSim->bhr_mask = b > 0 ? (1ULL << b) - 1 : 0;
    branchSim->bhr = 0;
    
    // Allocate predictor tables
    branchSim->counters = calloc(branchSim->predictor_size, sizeof(uint8_t));
    branchSim->btb = calloc(branchSim->predictor_size, sizeof(uint64_t));
    
    // Initialize all counters to 01 (weakly not taken)
    for (uint64_t i = 0; i < branchSim->predictor_size; i++) {
        branchSim->counters[i] = 1; // 01 state
    }
}

branch* init(branch_sim_args* csa)
{
    int op;
    uint64_t p = 0, s = 0, b = 0, g = 0;

    // TODO - get argument list from assignment
    while ((op = getopt(csa->arg_count, csa->arg_list, "p:s:b:g:")) != -1)
    {
        switch (op)
        {
            // Processor count
            case 'p':
                p = atoi_safe(op, optarg);
                break;

                // predictor size
            case 's':
                s = atoi_safe(op, optarg);
                break;

                // BHR size
            case 'b':
                b = atoi_safe(op, optarg);
                break;
                // predictor model
            case 'g':
                g = atoi_safe(op, optarg);
                break;
        }
    }

    init_branchSim(p, s, b, g);
    self = malloc(sizeof(branch));
    self->branchRequest = branchRequest;
    self->si.tick = tick;
    self->si.finish = finish;
    self->si.destroy = destroy;

    return self;
}

// Given a branch operation, return the predicted PC address
uint64_t branchRequest(trace_op* op, int processorNum)
{
    assert(op != NULL);
    assert(branchSim != NULL);

    uint64_t pcAddress = op->pcAddress;
    uint64_t predAddress = op->nextPCAddress; // 100% accuracy

    // In student's simulator, either return a predicted address from BTB
    //   or pcAddress + 4 as a simplified "not taken".
    // Predictor has the actual nextPCAddress, so it knows how to update
    //   its state after computing the prediction.
    
    // Get predictor index based on model
    uint64_t index = get_predictor_index(pcAddress, branchSim->bhr, branchSim->g, 
                                        branchSim->s, branchSim->b);
    
    // Make prediction based on counter value
    uint8_t counter = branchSim->counters[index];
    uint64_t predictedPC;
    int predicted_taken;
    
    if (counter >= 2) { // 10 or 11 - predict taken
        predicted_taken = 1;
        predictedPC = branchSim->btb[index];
        // If BTB entry is 0 or invalid, predict PC + 4
        if (predictedPC == 0) {
            predictedPC = pcAddress + 4;
            predicted_taken = 0;
        }
    } else { // 00 or 01 - predict not taken
        predicted_taken = 0;
        predictedPC = pcAddress + 4;
    }
    
    // Determine if branch was actually taken
    int actual_taken = (predAddress != pcAddress + 4) ? 1 : 0;
    
    // Update predictor state
    // Update counter
    if (actual_taken) {
        if (branchSim->counters[index] < 3) {
            branchSim->counters[index]++;
        }
    } else {
        if (branchSim->counters[index] > 0) {
            branchSim->counters[index]--;
        }
    }
    
    // Update BTB if branch was taken
    if (actual_taken) {
        branchSim->btb[index] = predAddress;
    }
    
    // Update BHR (shift left and add new outcome)
    if (branchSim->b > 0) {
        branchSim->bhr = ((branchSim->bhr << 1) | actual_taken) & branchSim->bhr_mask;
    }
    
    return predictedPC;
}

int tick()
{
    return 1;
}

int finish(int outFd)
{
    return 0;
}

int destroy(void)
{
    // free any internally allocated memory here
    if (branchSim != NULL) {
        if (branchSim->counters != NULL) {
            free(branchSim->counters);
        }
        if (branchSim->btb != NULL) {
            free(branchSim->btb);
        }
        free(branchSim);
        branchSim = NULL;
    }
    
    if (self != NULL) {
        free(self);
        self = NULL;
    }
    
    return 0;
}
