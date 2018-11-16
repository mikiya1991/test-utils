#include <string.h>
#include <stdio.h>
#include "stream_interface.h"

#define ARRAY_SIZE(x) (sizeof(x) / sizeof(x[0]))
static stream_builder *g_stream[16] = {0};

stream_builder *factory_find_stream(char *name)
{
	int i;
	stream_builder *ps;

	for (i = 0; ps = g_stream[i], i < ARRAY_SIZE(g_stream); i++) {
		if (ps) {
			if (!strcmp(name, ps->name))
				return ps;
		}
	}

	return NULL;
}


int register_stream(stream_builder *b)
{
	int i;
	stream_builder **ps;

	for (i = 0; ps = &g_stream[i], i < ARRAY_SIZE(g_stream); i++) {

		if (*ps == NULL) {
			*ps = b;
			return i;
		}
	}

	return -1;
}

