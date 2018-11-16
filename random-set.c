#include <unistd.h>
#include <stdio.h>
#include <string.h>
#include <signal.h>
#include <stdlib.h>
#include <time.h>
#include <inttypes.h>
#include <sys/types.h>

#define PAGES 1024
#define PAGE_SIZE (4 * 1024)


int64_t last_measure_time;
uint32_t last_measure_bytes;
int gbps;
pid_t pid;


int64_t __getts(void)
{
	struct timespec tv;

	clock_gettime(CLOCK_MONOTONIC, &tv);
	return (int64_t)tv.tv_sec * 1000000 + tv.tv_nsec / 1000;
}

double get_bps(uint32_t bytes, int64_t ts)
{
	double bps = ((double)(bytes - last_measure_bytes)
			/ ((ts - last_measure_time) / 1000000.0));

	last_measure_time = ts;
	last_measure_bytes = bytes;
	return bps;
}


void test(void) {
	uint32_t bytes = 0;
	char buffer[PAGES * PAGE_SIZE] = {0};
	int i;
	int greater_count = 1;
	int less_count = 1;
	int64_t last_show_time = __getts();

	srandom(time(NULL));
	last_measure_time = __getts();
	while (1) {
		int64_t tnow;
		double bps;

		for (i = 0; i < PAGE_SIZE * greater_count; i++)
			buffer[random() % (PAGE_SIZE * PAGES)] = i & 0xff;

		bytes += PAGE_SIZE * greater_count;
		if (less_count > 1)
			usleep((less_count - 1) * 4000);

		tnow = __getts();
		bps = get_bps(bytes, tnow);

		if (bps > gbps * 3 / 2 || bps < gbps / 2) {
			if (bps > gbps) {
				if (greater_count > 1)
					greater_count--;
				else
					less_count++;
			} else if (bps < gbps) {
				if (less_count > 1)
					less_count--;
				else
					greater_count++;
			}

			if (greater_count > 256)
				greater_count = 256;
			if (less_count > 250)
				less_count = 250;
			//printf("greater_count %d\t less_count %d\n", greater_count, less_count);
		}

		if (tnow - last_show_time >= 2000000) {
			double kbytes = bps / 1024;
			double mbytes = kbytes / 1024;

			if (kbytes > 1024)
				printf("[%d] bps %.2fMBps\n",pid, mbytes);
			else
				printf("[%d] bps %.2fKBps\n",pid, kbytes);
			last_show_time = tnow;
		}
	}
}


int main(int argc, const char * argv[])
{

	if (argc < 2) {
		fprintf(stderr, "This tool write 4M ddr, with a specified Bps\n");
		fprintf(stderr, "specify Bps\n");
		exit(-1);
	}

	gbps = atoi(argv[1]);

	pid = getpid();
	test();

	return 0;
}
