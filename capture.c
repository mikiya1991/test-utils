#include <inttypes.h>
#include <errno.h>
#include <time.h>
#include <unistd.h>
#include <string.h>
#include <stdlib.h>

#include <rtsavapi.h>
#include <rtsvideo.h>
#include <rts_errno.h>
#include "stream_interface.h"

struct rts_stream {
	int isp_ch;
	int h264_ch;
	int ch;
};

static int64_t __get_ts(void)
{
	struct timespec t;

	clock_gettime(CLOCK_MONOTONIC, &t);

	return (int64_t)t.tv_sec * 1000000 + t.tv_nsec/1000;
}

static int __create_h264_ch(rts_build_cfg *cfg)
{
	struct rts_h264_attr h264_attr;

	h264_attr.level = cfg->h264_level;
	h264_attr.qp = -1;
	h264_attr.bps = cfg->bitrate;
	h264_attr.gop = 30;
	h264_attr.videostab = 0;
	h264_attr.rotation = RTS_AV_ROTATION_0;

	return rts_av_create_h264_chn(&h264_attr);
}

static int __set_profile(int isp_ch, rts_build_cfg *cfg)
{
	struct rts_av_profile profile;

	profile.fmt = RTS_V_FMT_YUV420SEMIPLANAR;
	profile.video.width = cfg->w;
	profile.video.height = cfg->h;
	profile.video.numerator = 1;
	profile.video.denominator = cfg->fps;

	return rts_av_set_profile(isp_ch, &profile);
}

static int __create_h265_ch(rts_build_cfg *wcfg)
{
	return 0;
}

static int __create_isp_ch(rts_build_cfg *cfg)
{
	struct rts_isp_attr attr;
	int isp_ch;

	attr.isp_id = cfg->isp_id;
	attr.isp_buf_num = cfg->v4l2_buf_num;

	return rts_av_create_isp_chn(&attr);
}

static void *__create_stream(void *wcfg)
{
	int isp_ch;
	int h264_ch = -1;
	int ret = 0;
	struct rts_stream *st = malloc(sizeof(struct rts_stream));

	if (!st)
		return NULL;

	st->isp_ch = -1;
	st->h264_ch = -1;
	st->ch = -1;

	rts_av_init();
	rts_build_cfg *cfg = (rts_build_cfg *)wcfg;

	isp_ch = __create_isp_ch(cfg);
	if (isp_ch < 0) {
		ret = isp_ch;
		goto fail;
	}

	ret = __set_profile(isp_ch, cfg);
	if (ret < 0)
		goto fail;

	if (cfg->bool_h264) {
		h264_ch = __create_h264_ch(cfg);
		if (h264_ch < 0) {
			ret = h264_ch;
			goto fail;
		}
	}

	if (h264_ch < 0) {
		ret = rts_av_enable_chn(isp_ch);
		if (ret < 0)
			goto fail;

		ret = rts_av_start_recv(isp_ch);
		if (ret < 0)
			goto fail;

		st->isp_ch = isp_ch;
		st->ch = isp_ch;
	} else {
		ret = rts_av_bind(isp_ch, h264_ch);
		if (ret < 0)
			goto fail;
		ret = rts_av_enable_chn(isp_ch);
		if (ret < 0)
			goto fail;
		ret = rts_av_enable_chn(h264_ch);
		if (ret < 0)
			goto fail;
		ret = rts_av_start_recv(h264_ch);
		if (ret < 0)
			goto fail;

		st->isp_ch = isp_ch;
		st->h264_ch = h264_ch;
		st->ch = h264_ch;
	}

	return st;
fail:
	errno = ret;
	if (isp_ch > 0)
		rts_av_destroy_chn(isp_ch);

	if (h264_ch > 0)
		rts_av_destroy_chn(h264_ch);

	free(st);
	rts_av_release();

	return NULL;
}

static int __get_stream(void *handle, void *buf, uint32_t len,  int timeout_ms)
{
	int ch = ((struct rts_stream *)handle)->ch;
	int ret = 0;
	int ts_last, ts_now;
	struct rts_av_buffer *b;
	int bytes2cp;

	if (ch < 0) {
		ret = RTS_ERRNO(RTS_E_INVALID_ARG);
		goto fail;
	}

	ts_last = __get_ts();
	while (timeout_ms > 0) {
		ret = rts_av_poll(ch);
		if (ret < 0)
			goto next;

		ret = rts_av_recv(ch, &b);
		if (ret < 0)
			goto next;

		if (len < b->bytesused)
			bytes2cp = len;
		else
			bytes2cp = b->bytesused;

		memcpy((uint8_t *)buf, b->vm_addr, bytes2cp);
		rts_av_put_buffer(b);
		return bytes2cp;
next:
		usleep(4000);
		ts_now = __get_ts();
		timeout_ms -= (ts_now - ts_last) / 1000;
		ts_last = ts_now;
	}

	ret = RTS_ERRNO(RTS_E_TIMEOUT);

fail:
	errno = ret;
	return ret;
}

static void __destroy_stream(void *handle)
{
	struct rts_stream *st = (struct rts_stream *)handle;

	if (!st)
		return;

	if (st->isp_ch > 0)
		rts_av_destroy_chn(st->isp_ch);

	if (st->h264_ch > 0)
		rts_av_destroy_chn(st->h264_ch);

	rts_av_release();

	free(st);
}

static char *__get_error(void)
{
	return rts_strerrno(errno);
}

static stream_builder rts_video_stream = {
	.name = "rtstream",
	.create_stream = __create_stream,
	.recv_stream = __get_stream,
	.destroy_stream = __destroy_stream,
	.get_lasterror = __get_error,
};

register(rts_video_stream)
