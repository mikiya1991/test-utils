#include <stdio.h>
#include <errno.h>

#include "stream_interface.h"


int main(int argc, char *argv[])
{
	void *h;
	char buf[2048000];
	int nr_frames = 100;
	rts_build_cfg cfg = {
		.isp_id = 0,
		.v4l2_buf_num = 3,
		.w = 1280,
		.h = 720,
		.fps = 15,
		.bool_h264 = 1,
		.h264_level = 41,
		.bitrate = 2 * 1024 * 1024,
	};

	if (argc < 2)
		return -1;

	stream_builder *builder = factory_find_stream(argv[1]);

	if (!builder)
		return -1;

	printf("find builder(%s) %p\n", builder->name, builder);

	h = builder->create_stream(&cfg);
	if (!h)
		goto fail;

	printf("create_stream success\n");

	while (nr_frames--) {
		int len;

		len = builder->recv_stream(h, buf, sizeof(buf), 1000);
		if (len < 0)
			goto fail;

		printf("get bufsize %d\n", len);
	}

	builder->destroy_stream(h);

	return 0;

fail:
	printf("%s\n", builder->get_lasterror());
	return -1;
}
