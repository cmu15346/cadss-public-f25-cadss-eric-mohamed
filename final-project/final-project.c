#include <branch.h>
#include <trace.h>

#include <getopt.h>
#include <stdlib.h>
#include <assert.h>
#include <stdio.h>
#include <math.h>

typedef struct branch_def {
    // Simulation parameters
    uint64_t p; // number of processors
    uint64_t s; // predictor size 
    uint64_t b; // BHR size 
    uint64_t g; // predictor model 

    // Perceptron state
    int* weights;         // Table of weights (flattened 2D array)
    uint64_t* btb;        // Branch Target Buffer
    uint64_t bhr;         // Global Branch History Register
    
    // Derived values
    uint64_t num_perceptrons;   // 1 << s
    uint64_t index_mask;        // (1 << s) - 1
    uint64_t bhr_mask;          // (1 << b) - 1
    
    // Perceptron specific values
    int threshold;              // Training threshold (theta)
    int weights_per_row;        // b + 1 (history + bias)

    // Statistics
    uint64_t stat_total_branches;
    uint64_t stat_correct_predictions;
    uint64_t stat_mispredictions;
} branch_def;

branch* self = NULL;
branch_def* branchSim = NULL;

// Function declarations
uint64_t branchRequest(trace_op* op, int processorNum);
int tick();
int finish(int outFd);
int destroy(void);

uint64_t atoi_safe(int opt, char *string){
    int result = atoi(string);
    if (result == 0 && string[0] != '0'){
        fprintf(stderr, "Option -%c requires an integer argument.\n", opt);
        exit(0);
    }
    return result;
}

// Get predictor index based on PC and model type
uint64_t get_predictor_index(uint64_t pc, uint64_t bhr, uint64_t model, uint64_t s, uint64_t b) {
    uint64_t index_mask = (1ULL << s) - 1; // mask for s bits
    uint64_t pc_index = (pc >> 2) & index_mask; // Shift by 2 (instruction aligned)
    
    switch(model) {
        case 0: // Standard Perceptron (PC only)
            return pc_index;            
        case 1: // Gshare-style Indexing (PC XOR BHR)
            return (pc_index ^ bhr) & index_mask;
        case 2: // Gselect-style Indexing (Concat PC and BHR)
            // Uses 'b' bits of BHR and 's-b' bits of PC
            if (b >= s) return pc_index; 
            else {
                uint64_t pc_bits = (s - b);
                uint64_t pc_mask = (1ULL << pc_bits) - 1;
                // Combine: Top bits from BHR, Bottom bits from PC
                return ((pc_index & pc_mask) | ((bhr & ((1ULL << b) - 1)) << pc_bits)) & index_mask;
            }
            
        default: // Default to Standard
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
    
    // Derived values
    branchSim->num_perceptrons = 1ULL << s;
    branchSim->index_mask = branchSim->num_perceptrons - 1;
    branchSim->bhr_mask = b > 0 ? (1ULL << b) - 1 : 0;
    branchSim->bhr = 0;
    
    // Perceptron Parameters
    // Formula from paper: theta = floor(1.93 * h + 14)
    branchSim->threshold = (int)(1.93 * b + 14);
    branchSim->weights_per_row = b + 1;
    
    // Allocate tables
    branchSim->weights = calloc(branchSim->num_perceptrons * branchSim->weights_per_row, sizeof(int));
    branchSim->btb = calloc(branchSim->num_perceptrons, sizeof(uint64_t));
    
    // Initialize stats
    branchSim->stat_total_branches = 0;
    branchSim->stat_correct_predictions = 0;
    branchSim->stat_mispredictions = 0;
}

branch* init(branch_sim_args* csa)
{
    int op;
    uint64_t p = 0, s = 0, b = 0, g = 0;

    while ((op = getopt(csa->arg_count, csa->arg_list, "p:s:b:g:")) != -1)
    {
        switch (op)
        {
            case 'p': p = atoi_safe(op, optarg); break;
            case 's': s = atoi_safe(op, optarg); break;
            case 'b': b = atoi_safe(op, optarg); break;
            case 'g': g = atoi_safe(op, optarg); break;
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

uint64_t branchRequest(trace_op* op, int processorNum)
{
    assert(op != NULL);
    assert(branchSim != NULL);

    uint64_t pcAddress = op->pcAddress;
    uint64_t nextPC = op->nextPCAddress; 

    // Get Perceptron Index based on model
    uint64_t index = get_predictor_index(pcAddress, branchSim->bhr, branchSim->g, 
                                        branchSim->s, branchSim->b);
    
    int* w = &branchSim->weights[index * branchSim->weights_per_row];

    // Compute y = w0 + w1*x1 + w2*x2 + ... + wb*xb
    int y = w[0]; // Bias
    for (int i = 1; i <= branchSim->b; i++) {
        int history_bit = (branchSim->bhr >> (i - 1)) & 1;
        if (history_bit) y += w[i];
        else             y -= w[i];
    }

    // Make Prediction
    int predicted_taken = (y >= 0) ? 1 : 0;
    
    // If predicted taken, get target from BTB
    uint64_t predictedPC;
    if (predicted_taken) {
        predictedPC = branchSim->btb[index];
        // If BTB entry is 0 or invalid, predict PC + 4
        if (predictedPC == 0) {
             predictedPC = pcAddress + 4; 
             predicted_taken = 0; 
        }
    } else { // Predict not taken
        predictedPC = pcAddress + 4;
    }

    // Update Statistics
    branchSim->stat_total_branches++;
    if (predictedPC == nextPC) {
        branchSim->stat_correct_predictions++;
    } else {
        branchSim->stat_mispredictions++;
    }

    // Update Weights
    int actual_taken = (nextPC != pcAddress + 4) ? 1 : 0;
    int t = actual_taken ? 1 : -1; 

    if ((predicted_taken != actual_taken) || (abs(y) <= branchSim->threshold)) {
        w[0] += t;
        for (int i = 1; i <= branchSim->b; i++) {
            int history_bit = (branchSim->bhr >> (i - 1)) & 1;
            int x = history_bit ? 1 : -1;
            w[i] += t * x;
        }
    }

    // Update BTB if branch was taken
    if (actual_taken) {
        branchSim->btb[index] = nextPC;
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
    if (branchSim) {
        uint64_t total = branchSim->stat_total_branches;
        uint64_t correct = branchSim->stat_correct_predictions;
        uint64_t miss = branchSim->stat_mispredictions;
        double accuracy = (total > 0) ? (double)correct / total * 100.0 : 0.0;
        double miss_rate = (total > 0) ? (double)miss / total * 100.0 : 0.0;

        dprintf(outFd, "-----------------------------------------------------\n");
        dprintf(outFd, "              PERCEPTRON PREDICTOR STATS             \n");
        dprintf(outFd, "-----------------------------------------------------\n");
        dprintf(outFd, "Config: s=%lu, b=%lu, g=%lu\n", branchSim->s, branchSim->b, branchSim->g);
        dprintf(outFd, "Total Branches      : %lu\n", total);
        dprintf(outFd, "Correct Predictions : %lu\n", correct);
        dprintf(outFd, "Mispredictions      : %lu\n", miss);
        dprintf(outFd, "Accuracy            : %.4f%%\n", accuracy);
        dprintf(outFd, "Misprediction Rate  : %.4f%%\n", miss_rate);
        dprintf(outFd, "-----------------------------------------------------\n");
    }
    return 0;
}

int destroy(void)
{
    if (branchSim != NULL) {
        if (branchSim->weights != NULL) free(branchSim->weights);
        if (branchSim->btb != NULL) free(branchSim->btb);
        free(branchSim);
        branchSim = NULL;
    }
    if (self != NULL) {
        free(self);
        self = NULL;
    }
    return 0;
}