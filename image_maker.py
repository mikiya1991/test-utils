#!/usr/bin/python3
import os
import re
import subprocess
import sys

class SDK:
	def __init__(self, root, board = "rts3913l_evb", fw = ""):
		config = {}
		config["board"] = board
		config["sdkroot"] = root
		config["sysroot"] = "{}/out/{}".format(root, board)
		board_dts_file = config["sysroot"] + "/build/linux-custom/arch/rlx/boot/dts/realtek"+board+".dts"
		if fw:
			config["fw"] = config["sysroot"] + "/suitcase/" + fw
		else:
			config["fw"] = ""

		config["ddr-type"] = "config"
		config["ddr-file"] = config["sysroot"] + "/build/uboot-custom/u-boot.cfg.configs"
		config["ddr-prefix"] = "CONFIG_DDR_"

		config["cpu-type"] = "config"
		config["cpu-file"] = config["sysroot"] + "/build/uboot-custom/u-boot.cfg.configs"
		config["cpu-prefix"] = "CONFIG_CPU_"

		config["video-resv-mem-type"] = "dts"
		config["video-resv-mem-file"] = board_dts_file
		config["video-resv-mem-prefix"] = "reserved-memory:videomem:size"

		config["h265-clock-type"] = "dts"
		config["h265-clock-file"] = board_dts_file
		config["h265-clock-prefix"] = "rts_h265_vpucodec@0x180c0000:clock-frequency:<0 0 150000000 150000000>"

		config["h264-clock-type"] = "dts"
		config["h264-clock-file"] = board_dts_file
		config["h264-clock-prefix"] = "rts_h265_vpucodec@0x180c0000:clock-frequency:<0 0 150000000 150000000>"


		self.config = config
		self.board_dts_file = board_dts_file
		self.rebuild = {"kernel": 0, "uboot": 0, "user": 0}
		self.launch()

	def launch(self):
		subprocess.run("cd {}; ./launch.sh {}_defconfig".format(self.config["sdkroot"], self.config["board"]), shell = True)

	def __setitem__(self, key, val):
		if self.config[key + "-type"] == "config":
			self.__set_config(key, val)
		if self.config[key + "-type"] == "dts":
			self.__set_dts(key, val)

	def __set_config(self, key, val):
		key = key.lower()
		filename = self.config[key + "-file"]
		prefix = self.config[key + "-prefix"]

		with open(filename, "r") as f:
			text = f.read()
			text_after = re.sub(prefix + r"\d+", prefix + str(val), text)

		with open(filename, "w") as f:
			f.write(text_after)

		print("set-"+key+" {} in[{}] success".format(prefix + str(val), filename))

		self.rebuild["uboot"] = 1

	def __set_dts(self, key, val):
		pass

	def __copy_fw(self):
		if self.config["fw"]:
			subprocess.run("cp {} {}/suitcase/isp.fw".format(self.config["fw"], self.config["sysroot"]))
		else:
			print("no fireware specify, may using default", file=sys.stderr)
			fw_path = "{}/suitcase/isp.fw".format(self.config["sysroot"])
			if not os.access(fw_path, os.F_OK):
				print("there is no isp.fw in {}, ignoring...".format(fw_path), file=sys.stderr)

	def make(self):
		while True:
			print("\nready to make\npress Y/n to continue...")
			k = input()
			if k == "y" or k == "Y":
				self.__copy_fw()
				if self.rebuild["kernel"]:
					subprocess.run("cd {} && make linux".format(self.config["sysroot"]), shell = True)
				if self.rebuild["uboot"]:
					subprocess.run("cd {} && make uboot".format(self.config["sysroot"]), shell = True)

				subprocess.run("cd {} && make && make pack".format(self.config["sysroot"]), shell = True)

				subprocess.run("cp {}/images/linux.bin ./{}-linux.bin".format(self.config["sysroot"], self.config["board"]), shell = True)
				subprocess.run("cp {}/images/u-boot.bin ./{}-uboot.bin".format(self.config["sysroot"], self.config["board"]), shell = True)
				break

			if k == "n" or k == "n":
				break


sdk = SDK("/home/mikiya/workspace/sdk-master", "rts3913l_evb")

sdk["ddr"] = 1066
sdk["cpu"] = "500M"
sdk.make()
