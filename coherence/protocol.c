#include "coher_internal.h"

void sendBusRd(uint64_t addr, int procNum)
{
    inter_sim->busReq(BUSRD, addr, procNum);
}

void sendBusWr(uint64_t addr, int procNum)
{
    inter_sim->busReq(BUSWR, addr, procNum);
}

void sendData(uint64_t addr, int procNum)
{
    inter_sim->busReq(DATA, addr, procNum);
}

void indicateShared(uint64_t addr, int procNum)
{
    inter_sim->busReq(SHARED, addr, procNum);
}

coherence_states
cacheMI(uint8_t is_read, uint8_t* permAvail, coherence_states currentState,
        uint64_t addr, int procNum)
{
    switch (currentState)
    {
        case INVALID:
            *permAvail = 0;
            sendBusWr(addr, procNum);
            return INVALID_MODIFIED;
        case MODIFIED:
            *permAvail = 1;
            return MODIFIED;
        case INVALID_MODIFIED:
            fprintf(stderr, "IM state on %lx, but request %d\n", addr,
                    is_read);
            *permAvail = 0;
            return INVALID_MODIFIED;
        default:
            fprintf(stderr, "State %d not supported, found on %lx\n",
                    currentState, addr);
            break;
    }

    return INVALID;
}

coherence_states
snoopMI(bus_req_type reqType, cache_action* ca, coherence_states currentState,
        uint64_t addr, int procNum)
{
    *ca = NO_ACTION;
    switch (currentState)
    {
        case INVALID:
            return INVALID;
        case MODIFIED:
            sendData(addr, procNum);
            // indicateShared(addr, procNum); // Needed for E state
            *ca = INVALIDATE;
            return INVALID;
        case INVALID_MODIFIED:
            if (reqType == DATA || reqType == SHARED)
            {
                *ca = DATA_RECV;
                return MODIFIED;
            }

            return INVALID_MODIFIED;
        default:
            fprintf(stderr, "State %d not supported, found on %lx\n",
                    currentState, addr);
            break;
    }

    return INVALID;
}

// Feature table shared by all coherence schemes
typedef struct _scheme_features
{
    uint8_t hasExclusive; // Whether the protocol supports E (clean exclusive)
    uint8_t hasOwned;     // Whether dirty sharing transitions to the Owned state
    uint8_t hasForward;   // Whether a single sharer forwards future BusRd data
} scheme_features;

static const scheme_features schemeFeatureTable[] = {
    [MI] = {.hasExclusive = 0, .hasOwned = 0, .hasForward = 0},
    [MSI] = {.hasExclusive = 0, .hasOwned = 0, .hasForward = 0},
    [MESI] = {.hasExclusive = 1, .hasOwned = 0, .hasForward = 0},
    [MOESI] = {.hasExclusive = 1, .hasOwned = 1, .hasForward = 0},
    [MESIF] = {.hasExclusive = 1, .hasOwned = 0, .hasForward = 1},
};

// Common functions for shared protocols
static coherence_states cacheSharedProtocols(const scheme_features* feat,
                                             uint8_t is_read,
                                             uint8_t* permAvail,
                                             coherence_states currentState,
                                             uint64_t addr, int procNum)
{
    switch (currentState)
    {
        case INVALID:
            *permAvail = 0;
            if (is_read)
            {
                sendBusRd(addr, procNum);
                return COHER_INVALID_SHARED;
            }

            sendBusWr(addr, procNum);
            return INVALID_MODIFIED;

        case COHER_SHARED:
        case COHER_FORWARD:
            if (is_read)
            {
                *permAvail = 1;
                return currentState;
            }

            *permAvail = 0;
            sendBusWr(addr, procNum);
            return COHER_SHARED_MODIFIED;

        case COHER_EXCLUSIVE:
            *permAvail = 1;
            if (is_read)
            {
                return COHER_EXCLUSIVE;
            }

            return MODIFIED;

        case MODIFIED:
            *permAvail = 1;
            return MODIFIED;

        case COHER_OWNED:
            if (is_read)
            {
                *permAvail = 1;
                return COHER_OWNED;
            }

            *permAvail = 0;
            sendBusWr(addr, procNum);
            return COHER_OWNED_MODIFIED;

        case COHER_INVALID_SHARED:
        case INVALID_MODIFIED:
        case COHER_SHARED_MODIFIED:
        case COHER_OWNED_MODIFIED:
            *permAvail = 0;
            return currentState;

        default:
            fprintf(stderr, "State %d not supported, found on %lx\n",
                    currentState, addr);
            break;
    }

    return INVALID;
}

static coherence_states resolvePendingRequest(const scheme_features* feat,
                                              bus_req_type reqType,
                                              cache_action* ca,
                                              coherence_states currentState)
{
    if (reqType != DATA && reqType != SHARED)
    {
        return currentState;
    }

    switch (currentState)
    {
        case COHER_INVALID_SHARED:
            *ca = DATA_RECV;
            if (reqType == DATA)
            {
                return feat->hasExclusive ? COHER_EXCLUSIVE : COHER_SHARED;
            }

            return feat->hasForward ? COHER_FORWARD : COHER_SHARED;

        case INVALID_MODIFIED:
        case COHER_SHARED_MODIFIED:
        case COHER_OWNED_MODIFIED:
            *ca = DATA_RECV;
            return MODIFIED;

        default:
            break;
    }

    fprintf(stderr,
            "Unexpected response %d while in state %d (pending request)\n",
            reqType, currentState);
    return currentState;
}

static coherence_states snoopSharedProtocols(const scheme_features* feat,
                                             bus_req_type reqType,
                                             cache_action* ca,
                                             coherence_states currentState,
                                             uint64_t addr, int procNum)
{
    *ca = NO_ACTION;

    if (reqType == DATA || reqType == SHARED)
    {
        return resolvePendingRequest(feat, reqType, ca, currentState);
    }

    switch (currentState)
    {
        case INVALID:
            return INVALID;

        case COHER_SHARED:
            if (reqType == BUSRD)
            {
                indicateShared(addr, procNum);
                return COHER_SHARED;
            }

            if (reqType == BUSWR)
            {
                *ca = INVALIDATE;
                return INVALID;
            }

            break;

        case COHER_FORWARD:
            if (reqType == BUSRD)
            {
                sendData(addr, procNum);
                indicateShared(addr, procNum);
                return COHER_SHARED;
            }

            if (reqType == BUSWR)
            {
                *ca = INVALIDATE;
                return INVALID;
            }

            break;

        case COHER_EXCLUSIVE:
            if (reqType == BUSRD)
            {
                sendData(addr, procNum);
                indicateShared(addr, procNum);
                return COHER_SHARED;
            }

            if (reqType == BUSWR)
            {
                sendData(addr, procNum);
                *ca = INVALIDATE;
                return INVALID;
            }

            break;

        case MODIFIED:
            if (reqType == BUSRD)
            {
                sendData(addr, procNum);
                indicateShared(addr, procNum);
                if (feat->hasOwned)
                {
                    return COHER_OWNED;
                }
                return COHER_SHARED;
            }

            if (reqType == BUSWR)
            {
                sendData(addr, procNum);
                *ca = INVALIDATE;
                return INVALID;
            }

            break;

        case COHER_OWNED:
            if (reqType == BUSRD)
            {
                sendData(addr, procNum);
                indicateShared(addr, procNum);
                return COHER_OWNED;
            }

            if (reqType == BUSWR)
            {
                sendData(addr, procNum);
                *ca = INVALIDATE;
                return INVALID;
            }

            break;

        case COHER_INVALID_SHARED:
        case INVALID_MODIFIED:
        case COHER_SHARED_MODIFIED:
        case COHER_OWNED_MODIFIED:
            return currentState;

        default:
            fprintf(stderr, "State %d not supported, found on %lx\n",
                    currentState, addr);
            break;
    }

    return INVALID;
}

coherence_states cacheMSI(uint8_t is_read, uint8_t* permAvail,
                          coherence_states currentState, uint64_t addr,
                          int procNum)
{
    return cacheSharedProtocols(&schemeFeatureTable[MSI], is_read, permAvail,
                                currentState, addr, procNum);
}

coherence_states snoopMSI(bus_req_type reqType, cache_action* ca,
                          coherence_states currentState, uint64_t addr,
                          int procNum)
{
    return snoopSharedProtocols(&schemeFeatureTable[MSI], reqType, ca,
                                currentState, addr, procNum);
}

coherence_states cacheMESI(uint8_t is_read, uint8_t* permAvail,
                           coherence_states currentState, uint64_t addr,
                           int procNum)
{
    return cacheSharedProtocols(&schemeFeatureTable[MESI], is_read, permAvail,
                                currentState, addr, procNum);
}

coherence_states snoopMESI(bus_req_type reqType, cache_action* ca,
                           coherence_states currentState, uint64_t addr,
                           int procNum)
{
    return snoopSharedProtocols(&schemeFeatureTable[MESI], reqType, ca,
                                currentState, addr, procNum);
}

coherence_states cacheMOESI(uint8_t is_read, uint8_t* permAvail,
                            coherence_states currentState, uint64_t addr,
                            int procNum)
{
    return cacheSharedProtocols(&schemeFeatureTable[MOESI], is_read,
                                permAvail, currentState, addr, procNum);
}

coherence_states snoopMOESI(bus_req_type reqType, cache_action* ca,
                            coherence_states currentState, uint64_t addr,
                            int procNum)
{
    return snoopSharedProtocols(&schemeFeatureTable[MOESI], reqType, ca,
                                currentState, addr, procNum);
}

coherence_states cacheMESIF(uint8_t is_read, uint8_t* permAvail,
                            coherence_states currentState, uint64_t addr,
                            int procNum)
{
    return cacheSharedProtocols(&schemeFeatureTable[MESIF], is_read,
                                permAvail, currentState, addr, procNum);
}

coherence_states snoopMESIF(bus_req_type reqType, cache_action* ca,
                            coherence_states currentState, uint64_t addr,
                            int procNum)
{
    return snoopSharedProtocols(&schemeFeatureTable[MESIF], reqType, ca,
                                currentState, addr, procNum);
}
