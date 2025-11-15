#ifndef COHER_INTERNAL_H
#define COHER_INTERNAL_H

#include <interconnect.h>
#include <stdio.h>

extern interconn* inter_sim;

// These states unify the lock-step state machines used by MSI/MESI/MOESI/MESIF.
// "INVALID_*" represent transient states while a miss is waiting on the bus,
// and *_MODIFIED captures upgrade transactions (e.g., S->M) that have not
// completed yet.  The lifetime of MIXED states is entirely within permReq /
// busReq and therefore never needs to be explicitly represented in the cache.
typedef enum _coherence_states
{
    UNDEF = 0, // As tree find returns NULL, we need an unused for NULL
    MODIFIED,
    INVALID,
    INVALID_MODIFIED,
    SHARED, // Clean shared state
    INVALID_SHARED, // Transient waiting for BusRd to complete
    SHARED_MODIFIED, // Transient waiting for BusRdX to complete
    EXCLUSIVE, // Clean exclusive ownership
    OWNED, // Clean shared ownership (dirty in another cache)
    OWNED_MODIFIED, // Transient waiting for BusRdX to complete
    FORWARD // MESIF's single-forwarder state
} coherence_states;

typedef enum _coherence_scheme
{
    MI,
    MSI,
    MESI,
    MOESI,
    MESIF
} coherence_scheme;

coherence_states
cacheMI(uint8_t is_read, uint8_t* permAvail, coherence_states currentState,
        uint64_t addr, int procNum);
coherence_states
snoopMI(bus_req_type reqType, cache_action* ca, coherence_states currentState,
        uint64_t addr, int procNum);

coherence_states cacheMSI(uint8_t is_read, uint8_t* permAvail,
                          coherence_states currentState, uint64_t addr,
                          int procNum);
coherence_states snoopMSI(bus_req_type reqType, cache_action* ca,
                          coherence_states currentState, uint64_t addr,
                          int procNum);

coherence_states cacheMESI(uint8_t is_read, uint8_t* permAvail,
                           coherence_states currentState, uint64_t addr,
                           int procNum);
coherence_states snoopMESI(bus_req_type reqType, cache_action* ca,
                           coherence_states currentState, uint64_t addr,
                           int procNum);

coherence_states cacheMOESI(uint8_t is_read, uint8_t* permAvail,
                            coherence_states currentState, uint64_t addr,
                            int procNum);
coherence_states snoopMOESI(bus_req_type reqType, cache_action* ca,
                            coherence_states currentState, uint64_t addr,
                            int procNum);

coherence_states cacheMESIF(uint8_t is_read, uint8_t* permAvail,
                            coherence_states currentState, uint64_t addr,
                            int procNum);
coherence_states snoopMESIF(bus_req_type reqType, cache_action* ca,
                            coherence_states currentState, uint64_t addr,
                            int procNum);

#endif
