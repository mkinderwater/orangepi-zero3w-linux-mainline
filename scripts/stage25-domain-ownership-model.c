/* SPDX-License-Identifier: GPL-2.0
 * Stage25: user-space C ownership model for A733 IOMMU domain/page-directory.
 * gcc -std=c11 -Wall -Wextra -Werror -pedantic -pthread -O2 \
 *     scripts/stage25-domain-ownership-model.c -o /tmp/stage25-domain-model
 * /tmp/stage25-domain-model
 *
 * Not kernel code. No hardware access. Failures return nonzero.
 */
#include <pthread.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_DOMAINS 16
#define CHECK(x) do { if (!(x)) { \
    fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #x); \
    exit(1); } } while (0)

typedef struct {
    uintptr_t directory;
    uint64_t generation;
    unsigned int maps;
    bool live;
    bool installed;
} owner;

typedef struct {
    pthread_mutex_t lock;
    owner entries[MAX_DOMAINS];
    unsigned int n_clients;
    uint64_t next_generation;
    bool cache_live;
    bool removed;
} controller;

typedef struct {
    uintptr_t directory;
    uint64_t generation;
} token;

static void setup(controller *c) {
    memset(c, 0, sizeof(*c));
    CHECK(pthread_mutex_init(&c->lock, NULL) == 0);
    c->cache_live = true;
}
static token allocate(controller *c, uintptr_t directory) {
    token t = {0, 0};
    CHECK(pthread_mutex_lock(&c->lock) == 0);
    if (c->cache_live && !c->removed && directory) {
        int free_slot = -1;
        bool collision = false;
        for (int i=0; i<MAX_DOMAINS; i++) {
            if (c->entries[i].live && c->entries[i].directory == directory)
                collision = true;
            if (free_slot < 0 && !c->entries[i].live)
                free_slot = i;
        }
        if (!collision && free_slot >= 0 &&
            c->next_generation < UINT64_MAX) {
            owner *e = &c->entries[free_slot];
            e->directory = directory;
            e->generation = ++c->next_generation;
            e->maps = 0;
            e->installed = false;
            e->live = true;
            t.directory = directory;
            t.generation = e->generation;
        }
    }
    CHECK(pthread_mutex_unlock(&c->lock) == 0);
    return t;
}
static owner *find(controller *c, token t) {
    for (int i=0; i<MAX_DOMAINS; i++) {
        owner *e=&c->entries[i];
        if (e->live && e->directory == t.directory &&
            e->generation == t.generation)
            return e;
    }
    return NULL;
}
static bool enter_map(controller *c, token t) {
    bool ok=false;
    CHECK(pthread_mutex_lock(&c->lock) == 0);
    owner *e=find(c,t);
    if (e && e->maps < UINT32_MAX) {
        e->maps++;
        ok=true;
    }
    CHECK(pthread_mutex_unlock(&c->lock) == 0);
    return ok;
}
static bool leave_map(controller *c, token t) {
    bool ok=false;
    CHECK(pthread_mutex_lock(&c->lock) == 0);
    owner *e=find(c,t);
    if (e && e->maps) {
        e->maps--;
        ok=true;
    }
    CHECK(pthread_mutex_unlock(&c->lock) == 0);
    return ok;
}
static bool activate(controller *c, token t) {
    bool ok=false;
    CHECK(pthread_mutex_lock(&c->lock) == 0);
    owner *e=find(c,t);
    /* No actual TTB write: only model the exclusive active owner. */
    if (e && c->n_clients) {
        for (int i=0; i<MAX_DOMAINS; i++)
            if (c->entries[i].live) c->entries[i].installed=false;
        e->installed=true;
        ok=true;
    }
    CHECK(pthread_mutex_unlock(&c->lock) == 0);
    return ok;
}
static bool deactivate(controller *c, token t) {
    bool ok=false;
    CHECK(pthread_mutex_lock(&c->lock) == 0);
    owner *e=find(c,t);
    if (e && e->installed) {
        e->installed=false;
        ok=true;
    }
    CHECK(pthread_mutex_unlock(&c->lock) == 0);
    return ok;
}
static bool release(controller *c, token t) {
    bool ok=false;
    CHECK(pthread_mutex_lock(&c->lock) == 0);
    owner *e=find(c,t);
    if (e && !e->installed && e->maps==0) {
        e->live=false;
        e->directory=0;
        ok=true;
    }
    CHECK(pthread_mutex_unlock(&c->lock) == 0);
    return ok;
}
static bool destroy_cache(controller *c) {
    bool ok=true;
    CHECK(pthread_mutex_lock(&c->lock) == 0);
    if (!c->cache_live || c->n_clients) ok=false;
    for (int i=0; i<MAX_DOMAINS; i++)
        if (c->entries[i].live) ok=false;
    if (ok) c->cache_live=false;
    CHECK(pthread_mutex_unlock(&c->lock) == 0);
    return ok;
}
static void client(controller *c, bool add) {
    CHECK(pthread_mutex_lock(&c->lock) == 0);
    if (add) c->n_clients++;
    else {
        CHECK(c->n_clients>0);
        c->n_clients--;
    }
    CHECK(pthread_mutex_unlock(&c->lock) == 0);
}
static void teardown(controller *c) {
    CHECK(destroy_cache(c));
    CHECK(pthread_mutex_destroy(&c->lock)==0);
}

/* Exercise actual C reference ownership logic, including generation ABA. */
int main(void) {
    controller c;
    setup(&c);
    token a=allocate(&c,0x1000), b=allocate(&c,0x2000);
    CHECK(a.generation!=0 && b.generation!=0 && a.generation!=b.generation);
    CHECK(allocate(&c,0x1000).generation==0); /* duplicate address */
    CHECK(!release(&c,(token){0x9999,1}));     /* unknown pointer */
    CHECK(!destroy_cache(&c));                /* two live domains */
    CHECK(enter_map(&c,a));
    CHECK(!release(&c,a));                    /* live map protects directory */
    CHECK(leave_map(&c,a));
    client(&c,true);
    CHECK(activate(&c,b));
    CHECK(!release(&c,b));                    /* active TTB protected */
    CHECK(activate(&c,a));                    /* domain switch */
    CHECK(release(&c,b));
    CHECK(!release(&c,b));                    /* repeat-free rejected */
    CHECK(!destroy_cache(&c));                /* active domain */
    CHECK(deactivate(&c,a));
    CHECK(release(&c,a));
    client(&c,false);
    token again=allocate(&c,0x1000);         /* same address, new owner */
    CHECK(again.generation!=0 && again.generation!=a.generation);
    CHECK(!release(&c,a));                   /* stale ABA token rejected */
    CHECK(release(&c,again));
    teardown(&c);
    puts("Stage25 C domain-ownership model: PASS");
    return 0;
}
