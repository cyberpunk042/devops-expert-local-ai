/* numa_shim.c — LD_PRELOAD shim to fake libnuma success on WSL (no /sys/devices/system/node).
 *
 * SUPERSEDED 2026-04-25 — only useful for the kt-kernel/sglang local serving path,
 * which was rejected on this hardware (see docs/POSTMORTEM-2026-04-24-k26-local-wrong-path.md).
 * The current local K2.6 stack uses llama.cpp (scripts/llama-serve.sh), which does NOT call
 * libnuma and does not need this shim. Kept for historical reference and in case a future
 * libnuma-using workload returns to this environment.
 *
 * WSL's kernel doesn't expose NUMA topology. kt-kernel's worker_pool.h calls
 *   numa_bitmask_alloc(numa_num_configured_nodes())  // passes 0 on WSL → "request to allocate mask for invalid number"
 *   numa_bind(mask)
 *   numa_node_of_cpu(sched_getcpu())
 * without first checking numa_available(). This shim pretends 1 NUMA node exists
 * and makes all binds no-ops so the calls succeed silently.
 *
 * Build:  gcc -shared -fPIC numa_shim.c -o numa_shim.so
 * Use:    LD_PRELOAD=/path/to/numa_shim.so kt run ...
 */
#include <stddef.h>
#include <stdlib.h>

struct bitmask {
    unsigned long size;
    unsigned long *maskp;
};

static unsigned long fake_mask_bits[1] = {1};
static struct bitmask fake_bm = {64, fake_mask_bits};

int numa_available(void) { return 0; }                                       /* "supported" */
int numa_num_configured_nodes(void) { return 1; }
int numa_num_possible_nodes(void) { return 1; }
int numa_num_configured_cpus(void) { return 8; }
int numa_num_possible_cpus(void) { return 8; }
int numa_max_node(void) { return 0; }
int numa_max_possible_node(void) { return 0; }
int numa_node_of_cpu(int cpu) { (void)cpu; return 0; }

struct bitmask *numa_bitmask_alloc(unsigned int n) { (void)n; return &fake_bm; }
struct bitmask *numa_allocate_nodemask(void) { return &fake_bm; }
struct bitmask *numa_bitmask_clearall(struct bitmask *bm) { return bm; }
struct bitmask *numa_bitmask_setbit(struct bitmask *bm, unsigned int n) { (void)n; return bm; }
struct bitmask *numa_bitmask_clearbit(struct bitmask *bm, unsigned int n) { (void)n; return bm; }
int numa_bitmask_isbitset(const struct bitmask *bm, unsigned int n) { (void)bm; (void)n; return 1; }
unsigned int numa_bitmask_weight(const struct bitmask *bm) { (void)bm; return 1; }
void numa_bitmask_free(struct bitmask *bm) { (void)bm; }
void numa_free_nodemask(struct bitmask *bm) { (void)bm; }

int numa_bind(struct bitmask *bm) { (void)bm; return 0; }
void numa_set_bind_policy(int strict) { (void)strict; }
void numa_set_localalloc(void) { }
void numa_set_preferred(int node) { (void)node; }
int numa_preferred(void) { return 0; }
void numa_set_membind(struct bitmask *bm) { (void)bm; }
struct bitmask *numa_get_membind(void) { return &fake_bm; }
struct bitmask *numa_get_run_node_mask(void) { return &fake_bm; }
void numa_bind_to_node(int node) { (void)node; }
long numa_node_size(int node, long *freep) { (void)node; if (freep) *freep = 0; return 0; }
long long numa_node_size64(int node, long long *freep) { (void)node; if (freep) *freep = 0; return 0; }

int numa_run_on_node(int node) { (void)node; return 0; }
int numa_run_on_node_mask(struct bitmask *bm) { (void)bm; return 0; }
struct bitmask *numa_get_interleave_mask(void) { return &fake_bm; }
void numa_set_interleave_mask(struct bitmask *bm) { (void)bm; }

/* memory allocation helpers — defer to plain malloc */
void *numa_alloc_onnode(size_t size, int node) { (void)node; return malloc(size); }
void *numa_alloc_interleaved(size_t size) { return malloc(size); }
void *numa_alloc_local(size_t size) { return malloc(size); }
void *numa_alloc(size_t size) { return malloc(size); }
void numa_free(void *p, size_t size) { (void)size; free(p); }
