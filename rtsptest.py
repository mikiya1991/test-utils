#!/usr/bin/python
import telnetlib
import urllib2
import subprocess as sb
import json
import time
from matplotlib import pyplot as pt
import re

class virtualShell:
    """
    init telnet
    """
    def __init__(self, host, username, port = 0, password = ""):
        tel = telnetlib.Telnet()
        if port > 0:
            tel.open(host, port)
        else:
            tel.open(host)
        buf = tel.read_until("login: ", 10)
        if buf.find("login") < 0:
            raise Exception("read for login timeout " + buf)
        tel.write(username + "\n")
        if password:
            buf = tel.read_until("Password: ", 10)
            if buf.find("Password") < 0:
                raise Exception("No Password get " + buf)
            tel.write(password + "\n")
        buf = tel.read_until("#", 10)
        if buf.find("#") < 0:
            raise Exception("login failed " + buf)
        self.telnet = tel
        self.timeout = 20

    def cmd(self, cmd):
        """
        exec a cmd and get output from telnet
        """
        tel = self.telnet
        tel.write(cmd + "\n")
        buf = tel.read_until("\n#", self.timeout)
        if buf.find("#") < 0:
            return (-1, buf)
        ret_str = buf.rstrip('\r\n#')
        ret_str = ret_str[ret_str.find('\r\n') + 2:]
        return (0, ret_str)

    def set_timeout(self, timeout):
        self.timeout = timeout

    def __del__(self):
        tel = self.telnet
        tel.write("exit\n")
        tel.close()


class testManager:
    def __init__(self, host, port = "43794", profile = "profile1"):
        self.host = host
        self.rtsp_port = port
        self.profile = profile
        self.username = "admin"
        self.password = "123456"
        self.rtsp_host = "rtsp://" + host + ":" + port + '/' + profile
        self.shell = virtualShell(host, "root")
        self.clients = []

    def get_running_clients_count(self):
        count = 0
        for c in self.clients:
            if c.poll() != None:
                print "a client exit ", c.wait()
                self.client.remove(c)
            else:
                count += 1
        return count

    def setup_n_clients(self, num):
        count = self.get_running_clients_count()
        while count != num:
            if count < num:
                for i in xrange(count + 1, num + 1):
                    self.clients.append(sb.Popen(["saber", "rtp", "-p", self.rtsp_host]))
            if count > num:
                for i in xrange(num + 1, count + 1):
                    self.clients[-1].terminate()
                    print "force exit client ", self.clients[-1].wait()
                    self.clients.pop()
            count = self.get_running_clients_count()

    def set_cgi_attr(self, cgi_uri, attr):
        """
        set stream attr
        @attr attr table e.g. {a:1, b:2}
        """
        auth_handler = urllib2.HTTPDigestAuthHandler()
        auth_handler.add_password("realsil", self.host, self.username, self.password)
        opener = urllib2.build_opener(auth_handler)
        urllib2.install_opener(opener)
        f = urllib2.urlopen("http://" + self.host + cgi_uri, data = json.dumps(attr))
        if f.getcode() != 200:
            return (-1)
        else:
            return 0

    def __set_stream_attr(self, attr):
        r = self.set_cgi_attr("/cgi-bin/stream.cgi", {"command":"setParam", "stream":self.profile, "data": attr})
        if r != 0:
            raise Exception("set stream attribute err")
        time.sleep(2)

    def set_bitrate(self, bitrate):
        self.__set_stream_attr({"bitrateMode":"CBR", "bitRate": bitrate})

    def set_resolution(self, resolution="1280x720"):
        self.__set_stream_attr({"resolution": resolution})

    def set_framerate(self, fps=25):
        self.__set_stream_attr({"fps": fps})

    def board_run_cmd(self, cmd):
        return self.shell.cmd(cmd)[-1]

    def __del__(self):
        for c in self.clients:
            c.kill()
            c.wait()

    def set_username_password(self, username, password):
        self.username = username
        self.password = password


class nClientsBitrateTest(testManager):
    """
    Test maxto s_clients_num rtsp_clients, using bitrate s_bitrate
    it is a TODO: how to permit situation that board oom-killer.
    that will case the test dead
    """
    s_bitrate = map(lambda x: 1024*1024*x, [2, 4, 8])
    s_clients_num = 16

    def __init__(self, *args):
        testManager.__init__(self, *args)

    def set_testcase(self, bitrates, clients_num_array):
        if len(bitrates) != len(clients_num_array):
            raise Exception("testcase unmatch")
        nClientsBitrateTest.s_bitrate = bitrates
        nClientsBitrateTest.s_clients_num = clients_num_array

    def __test(self):
        # t = sb.Popen("saber -S rtsp://10.0.2.111:43794/profile1 ", shell = True)
        t = sb.Popen(["saber", "rtp", "-p", "-d", "30", self.rtsp_host], stdout=sb.PIPE)
        ret_string = self.board_run_cmd("top -b -n 3")
        tt = 0
        end = 0
        while tt < 30 and not end:
            if t.poll() == None:
                time.sleep(5)
                tt += 5
            else:
                t.wait()
                end = 1
        if not end:
            t.kill()
            t.wait()
            raise Exception("subprocess not responsing, maybe board is die")
        if t.poll() != 0:
            raise Exception("performance test err %d"% (t.poll()))
        ret_overflow = self.board_run_cmd("cat /sys/devices/platform/ocp/18040000.rts_soc_camera/streaminfo")
        return (t.stdout.read(), ret_string, ret_overflow)

    def run(self):
        """
        this is a generator of testing log
        output : (top log, saber log)
        """
        for bitrate in nClientsBitrateTest.s_bitrate:
            self.m_bitrate = bitrate
            self.set_bitrate(bitrate)
            self.end_loop = 0
            for i in xrange(1, self.s_clients_num + 1):
                if self.end_loop:
                    break
                self.setup_n_clients(i - 1)
                self.m_testcount = i
                yield self.__test()
            self.setup_n_clients(0)

    def end_single_bitrate_test(self):
        self.end_loop = 1


class logParser(object):
    def __init__(self):
        if self.match_set:
            for k, v in self.match_set.iteritems():
                self.match_set[k] = re.compile(v, re.M)
            self.match_result = {}

    def parse(self, log):
        result = ""
        self.match_result.clear()
        for k, v in self.match_set.iteritems():
            match = None
            if v:
                match = v.search(log)
            if result:
                result = result + '\t'
            if match and match.groups():
                result = result + match.group(1)
                self.match_result[k] = match.group(1)
            else:
                raise Exception("parse err key <{}>, log: ----\n{}\n----\n".format(k, log))
        return result

    def titles(self):
        if self.match_set:
            return self.match_set.keys()
        else:
            return None

    def __getitem__(self, x):
        if self.match_result.has_key(x):
            return self.match_result[x]
        else:
            return None


class rtspParser(logParser):
    def __init__(self):
        self.match_set = {
            "kbps_ave": r"kbps_ave\s+(\d+\.\d+)",
            "fps_ave": r"fps_ave\s+(\d+\.\d+)",
            "jitter": r"jitter\(1/90000\)\s+(\d+)"
        }
        logParser.__init__(self)

class testParser(logParser):
    def __init__(self):
        self.match_set = {
            "CPU": r"CPU usage: (\d+\.\d+)% user",
            "Process": r"Processes: (\d+) total"
        }
        logParser.__init__(self)

class overflowParser(logParser):
    def __init__(self):
        self.match_set = {
            "overflow_stream0": r"^0\s+\d+\s+\d+\s+(\d+)",
            "overflow_stream1": r"^1\s+\d+\s+\d+\s+(\d+)",
            #"overflow_stream2": r"^2\s+\d+\s+\d+\s+\d+\s+\d+\s+\[\d+\]:\d+\s+\[\d+\]:\d+$",
        }
        logParser.__init__(self)


class topParser(logParser):
    def __init__(self):
        self.match_set = {
         "used": r"(\d+)K used",
         "free": r"(\d+)K free",
         "idle": r"(\d+\.\d)*% idle",
         "peacock_profile1": r"(\d+\.\d+) peacock\s+-p\s+profile1",
         "peacock_profile2": r"(\d+\.\d+) peacock\s+-p\s+profile2",
         "lark":  r"(\d+\.\d+) lark",
         "rtspd": r"(\d+\.\d+) rtspd"}
        logParser.__init__(self)

    def parse(self, log):
        # skip 2 top outputs, because of top -b -n3
        pos = 0
        for i in range(3):
            mo = re.search("Mem:", log[pos:])
            if mo:
                pos += mo.end()
            else:
                raise Exception("parsing err")
        pos -= len("Mem:")
        return super(topParserV3, self).parse(log[pos:])



class topParserV3(logParser):
    def __init__(self):
        self.match_set = {
         "used": r"(\d+)K used",
         "free": r"(\d+)K free",
         "idle": r"(\d+)% idle",
         "peacock_profile1": r"(\d+)% peacock\s+-p\s+profile1",
         "peacock_profile2": r"(\d+)% peacock\s+-p\s+profile2",
         "lark":  r"(\d+)% lark",
         "rtspd": r"(\d+)% rtspd"}
        logParser.__init__(self)

    def parse(self, log):
        # skip 2 top outputs, because of top -b -n3
        pos = 0
        for i in range(3):
            mo = re.search("Mem:", log[pos:])
            if mo:
                pos += mo.end()
            else:
                raise Exception("parsing err")
        pos -= len("Mem:")
        return super(topParserV3, self).parse(log[pos:])

class topParserV31(topParserV3):
    def __init__(self):
        self.match_set = {
         "used": r"(\d+)K used",
         "free": r"(\d+)K free",
         "idle": r"(\d+)% idle",
         "peacock_profile1": r"(\d+)% peacock",
         "lark":  r"(\d+)% lark",
         "rtspd": r"(\d+)% rtspd"}
        logParser.__init__(self)




def usage():
    print """Ipcam rtsp performance test tool
Usage:
{} test [options] hostaddr[:port]
{} plot <log1 log2 log3 ..>
{} tel -c cmd host

test: running rtsp performance test and generate report
plot: plot pictures according to report files
tel: run a command through telnet

generic options:
    -h show this help
test options:
    -o output report name
    -n don not parse logs, output origin logs
plot options:
    -l [label1: label2...]specify label of a plot
    -b specify bitrate of a plot
tel options:
    -c specify cmd
note: this tool need saber in executable path
""".format(app_name)
    exit(1)

def file_plot_label_bitrate(filename, label, bitrate):
    with open(filename, 'r') as fid:
        titles = fid.readline().rstrip('\n').split('\t')
        if not label in titles:
            raise Exception("file %s does not have label %s"%(filename, label))
        ilabel = titles.index(label)

        array = []
        pattern = re.compile(r"\[(\d+),\s*(\d+)\]")
        for l in fid.readlines():
            mo = pattern.match(l)
            if not mo:
                raise Exception("line format err %s"%(l))
            ibitrate = int(mo.group(1))
            #iclients = int(mo.group(2))
            if bitrate != ibitrate:
                continue
            ret = float(l[mo.end() :].rstrip('\n').split('\t')[ilabel])
            array.append(ret)
        pt.plot(range(1, len(array) + 1), array, '.-', label = "%s_%d"%(filename, bitrate))


app_name=""
if __name__ == "__main__":
    import sys
    import getopt

    app_name = sys.argv[0]
    if len(sys.argv) < 2:
        print "too few argments"
        usage()

    if sys.argv[1] == 'test':
        mode = 'test'
    elif sys.argv[1] == 'plot':
        mode = 'plot'
    elif sys.argv[1] == "parse":
        mode = 'parse'
    elif sys.argv[1] == "tel":
        mode = "tel"
    else:
        usage()


    try:
        opts, args = getopt.getopt(sys.argv[2:], "hno:l:b:c:")
    except getopt.GetoptError as err:
        print str(err)
        usage()

    outfile = None
    bitrate = 0
    label = ''
    bparse = True
    for o, v in opts:
        if o == "-h":
            usage()
        if o == '-o':
            outfile = open(v, "w+")
        if o == '-l':
            label = v
        if o == '-b':
            bitrate = int(v) * 1024 * 1024
        if o == '-c':
            cmd = v
        if o == '-n':
            bparse = False

    if mode == 'test':
        try:
            host = args[0]
            hostname = ''
            port = ''
            if ':' in host:
                hostname, port = host.split(':')
            else:
                hostname = host
            if port:
                tester = nClientsBitrateTest(host, port)
            else:
                tester = nClientsBitrateTest(host)

            tp = topParserV31()
            rp = rtspParser()
            op = overflowParser()
            title = reduce(lambda x, y: x+'\t'+y, tp.titles() + rp.titles() + op.titles())
            print title
            if outfile:
                print >> outfile, title
            for rtsplog, toplog, oplog in tester.run():
                tplog_parsed = tp.parse(toplog)
                rplog_parsed = rp.parse(rtsplog)
                oplog_parsed = op.parse(oplog)
                if bparse:
                    log = (str([tester.m_bitrate, tester.m_testcount])
                            + tplog_parsed + '\t' + rplog_parsed + "\t" + oplog_parsed)
                else:
                    log = toplog + '\n' + rtsplog
                print log
                if outfile:
                    print >> outfile, log

                if int(tp["idle"]) < 5 or float(rp["fps_ave"]) < 23:
                    print "reach max ability, single test break"
                    tester.end_single_bitrate_test()
        finally:
            if outfile:
                outfile.close()
            import os
            os.system("notify-send done " + host)

    elif mode == "parse":
        op = overflowParser()
        sh = virtualShell(args[0], "root")
        oplog = sh.cmd("cat /sys/devices/platform/ocp/18040000.rts_soc_camera/streaminfo")[-1]
        print op.titles()
        print op.parse(oplog)

    elif mode == "plot":
        if len(args) == 0:
            print "missing a argment"
            usage()
        if not label:
            label = ["idle", "free", "fps_ave", "kbps_ave"]
        else:
            if label.find(':') > 0:
                label = label.split(':')
            else:
                label = [label]

        if not bitrate:
            bitrate = map(lambda x:1024*1024*x, [2, 4, 8])
        else:
            bitrate = [bitrate]

        def plot_label(inlabel, infiles, inbitrates):
            for f in infiles:
                for bb in inbitrates:
                    file_plot_label_bitrate(f, inlabel, bb)
            pt.title(inlabel)
            pt.legend(loc='upper right')

        if len(label) == 1:
            plot_label(label[0], args, bitrate)
            pt.show()
        else:
            if len(label) >= 6:
                ncols= 3
            else:
                ncols= 2

            nrows, tail = divmod(len(label), ncols)
            if tail:
                nrows += 1

            pt.figure()
            i = 1
            for _l in label:
                pt.subplot(nrows, ncols, i)
                i += 1
                plot_label(_l, args, bitrate)
            pt.show()
    else:
        sh = virtualShell(args[0], "root")
        print sh.cmd(cmd)[-1]


    #os.system("notify-send done " + host)
