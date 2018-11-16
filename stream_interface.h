#ifndef __STREAM_INTERFACE_H__
#define __STREAM_INTERFACE_H__
#include <inttypes.h>
typedef struct {
	int isp_id;
	int v4l2_buf_num;
	int w;
	int h;
	int fps;

	char encoder[16];
	char level[16];
	char bitrate_mode[16];
	int bitrate;
	int max_bitrate;
	int min_bitrate;
} rts_build_cfg;

typedef struct {
	char name[16];
	void *(* create_stream)(void *cfg);
	int (* recv_stream)(void *h, void *buf, uint32_t len, int timeout_ms);
	void (* destroy_stream)(void *h);
	char *(* get_lasterror)(void);
	/* int (* set_fps)(void *, int fps); */
} stream_builder;

stream_builder *factory_find_stream(char *name);
int register_stream(stream_builder *b);

#define register(x) \
void __register_##x(void) __attribute__((constructor)); \
void __register_##x(void) \
{ \
	register_stream(&x); \
}

#endif
