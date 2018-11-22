#!/usr/bin/python
import telnetlib
import urllib2
import subprocess as sb
import json
import time
from matplotlib import pyplot as pt
import re
import sys

class TelShell:
    """
    A telnet control class. intend to run shell cmd through network
    """
    def __init__(self, host, username = "root", password = ""):
        tel = telnetlib.Telnet()
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
            raise Exception("telnet cmd error {}".format(buf))
        ret_str = buf.rstrip('\r\n#')
        ret_str = ret_str[ret_str.find('\r\n') + 2:]
        return ret_str

    def set_timeout(self, timeout):
        self.timeout = timeout

    def __del__(self):
        tel = self.telnet
        tel.write("exit\n")
        tel.close()


class CgiManager:
    def __init__(self, host, username = "Admin", password = "123456"):
        self.host = host
        self.username = username
        self.password = password

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

    def __set_stream_attr(self, attr, profile = "profile1"):
        r = self.set_cgi_attr("/cgi-bin/stream.cgi", {"command":"setParam", "stream":profile, "data": attr})
        if r != 0:
            raise Exception("set stream attribute err")
        time.sleep(2)

    def set_bitrate(self, bitrate):
        self.__set_stream_attr({"bitrateMode":"CBR", "bitRate": bitrate})

    def set_resolution(self, resolution="1280x720"):
        self.__set_stream_attr({"resolution": resolution})

    def set_framerate(self, fps=25):
        self.__set_stream_attr({"fps": fps})



class SaberManager:
    def __init__(self, rtspurl):
        self.url = rtspurl
        self.clients = []

    def get_running_clients_num(self):
        count = 0
        for c in self.clients:
            if c.poll() != None:
                print "A client exit ", c.wait()
                self.client.remove(c)
            else:
                count += 1
        return count

    def setup_n_clients(self, num):
        count = self.get_running_clients_num()
        while count != num:
            if count < num:
                for i in xrange(count + 1, num + 1):
                    self.clients.append(sb.Popen(["saber", "rtp", "-p", self.url]))
            if count > num:
                for i in xrange(num + 1, count + 1):
                    self.clients[-1].terminate()
                    print "force exit client ", self.clients[-1].wait()
                    self.clients.pop()
            count = self.get_running_clients_num()

    def run_nclients_nsec(self, clients_num, nsecs):
        self.setup_n_clients(clients_num - 1)
        return sb.Popen(["saber", "rtp", "-p", "-d", "{}".format(nsecs), self.url], stdout=sb.PIPE)

    def __del__(self):
        for c in self.clients:
            c.kill()
            c.wait()


class Tester:
    def __init__(self, rtspurl, **args):
        """
        args:
            rtspurl: rtsp addr for rtspclient
            cgi_user:
            cgi_password:
            telnet_user:
            telnet_password:
        """
        self.rtspurl = url
        self.host, self.port, self.profile = self.parse_url(rtspurl)
        self.cgi_auth = ["Admin", "123456"]
        self.telnet_auth = ["root", ""]
        for key, val in args.iteritems():
            if key is "cgi_user":
                self.cgi_auth[0] = val
            if key is "cgi_password":
                self.cgi_auth[1] = val
            if key is "telnet_user":
                self.telnet_auth[0] = val
            if key is "telnet_password":
                self.telnet_auth[1] = val

        self.telnet = TelShell(self.host, *self.telnet_auth)
        self.saber = SaberManager(rtspurl)
        self.cgi = CgiManager(self.host, *self.cgi_auth)

    def parse_url(self, url):
        if not url.startwiths("rtsp://"):
            raise Exception("Err, incorrect rtspurl")
        tail = url[len("rtsp://"):]
        host, tail = tail.split(':')
        if tail.find("/") > 0:
            port, profile = tail.split('/')
        else:
            profile = "profile1"
        port = int(port)
        return (host, port, profile)

    def __del__(self):
        del self.telnet

    def run_test(self, parser_list):
        pass


class BitrateTester(Tester):
    def run_test(self, parser_list):
        # this is a parsers responsibity chain mode
        bitrates = map(lambda x: 1024 * 1024 * x, [2, 4, 8])

        for bitrate in bitrates:
            self.cgi.set_bitrate(bitrate)

            for clients_num in xrange(1, 16):
                thread = self.saber.run_nclients_nsecs(clients_num, 30)
                toplog = self.telnet.cmd("top -b -n 3")
                timeout = 30

                while timeout > 0:
                    time.sleep(10)
                    timeout -= 10
                    if thread.poll() != None:
                        break

                if thread.poll() != None and thread.poll() == 0:
                    saberlog = thread.stdout.read()
                else:
                    raise Exception("Err, saber dead may oom!")

                overflow_log = self.telnet.cmd("cat /sys/devices/platform/ocp/18040000.rts_soc_camera/streaminfo")

                logs = {"saber": saberlog,
                       "overflow": overflow_log,
                       "top": toplog}

                if parser_list:
                    res = {"bitrate": bitrate, "clients": clients_num}
                    for p in parser_list:
                        res.update(p.parse(logs))

                    yield res
                    if res["fps_ave"] < 23 or res["idle"] < 5:
                        break
                else:
                    yield logs


class LogParser(object):
    def __init__(self):
        if self.match_set:
            for k, v in self.match_set.iteritems():
                self.match_set[k] = re.compile(v, re.M)

    def parse(self, logs):
        """
        parse will parse the log, which has key of its category.

        Return: the result as dict.
        """
        if not logs.has_key(self.category)
            return
        else:
            log = logs[self.category]
        res = {}
        for k, v in self.match_set.iteritems():
            match = v.search(log)
            if match and match.groups():
                res[k] = match.groups(1)
            else:
                raise Exception("parse err key <{}>, log: ----\n{}\n----\n".format(k, log))
        del log[self.category]
        return res


class RtspParser(LogParser):
    def __init__(self):
        self.category = "saber"
        self.match_set = {
            "kbps_ave": r"kbps_ave\s+(\d+\.\d+)",
            "fps_ave": r"fps_ave\s+(\d+\.\d+)",
            "jitter": r"jitter\(1/90000\)\s+(\d+)"
        }
        LogParser.__init__(self)

class OverflowParser(LogParser):
    def __init__(self):
        self.category = "overflow"
        self.match_set = {
            "overflow_stream0": r"^0\s+\d+\s+\d+\s+(\d+)",
            "overflow_stream1": r"^1\s+\d+\s+\d+\s+(\d+)",
        }
        LogParser.__init__(self)


class TopParserV3(LogParser):
    def __init__(self):
        self.category = "top"
        self.match_set = {
         "used": r"(\d+)K used",
         "free": r"(\d+)K free",
         "idle": r"(\d+)% idle",
         "peacock_profile1": r"(\d+)% peacock\s+-p\s+profile1",
         "peacock_profile2": r"(\d+)% peacock\s+-p\s+profile2",
         "lark":  r"(\d+)% lark",
         "rtspd": r"(\d+)% rtspd"}
        LogParser.__init__(self)

    def parse(self, logs):
        # skip 2 top outputs, because of top -b -n3
        if not logs.has_key(self.category)
            return
        log = logs[self.category]

        pos = 0
        for i in range(3):
            pos = log.find("Mem:", pos)
            if pos >= 0:
                pos = pos + len("Mem:")
            else:
                raise Exception("parsing err")
        pos -= len("Mem:")
        logs[self.category] = log[pos:]
        return super(topParserV3, self).parse(logs)

class TopParserV31(topParserV3):
    def __init__(self):
        self.category = "top"
        self.match_set = {
         "used": r"(\d+)K used",
         "free": r"(\d+)K free",
         "idle": r"(\d+)% idle",
         "peacock_profile1": r"(\d+)% peacock",
         "lark":  r"(\d+)% lark",
         "rtspd": r"(\d+)% rtspd"}
        LogParser.__init__(self)




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
""".format(sys.argv[0])
    exit(1)

def file_plot_label_bitrate(filename, label, bitrate):
    with open(filename, 'r') as fid:
        titles = fid.readline().rstrip('\n').split('\t')
        if not label in titles:
            raise Exception("file %s does not have label %s"%(filename, label))
        ilabel = titles.index(label)
        ibitrate = titles.index("bitrate")

        array = []
        for l in fid.readlines():
            #iclients = int(mo.group(2))
            lt = l.split('\t')
            if int(lt[ibitrate]) != bitrate:
                continue
            ret = float(lt[ilabel])
            array.append(ret)
        pt.plot(range(1, len(array) + 1), array, '.-', label = "%s_%d"%(filename, bitrate))


if __name__ == "__main__":
    import getopt

    if len(sys.argv) < 2:
        print "too few argments"
        usage()

    mode = sys.argv[1]
    if not mode in ["test", "plot", "parse", "tel"]:
        usage()

    try:
        opts, args = getopt.getopt(sys.argv[2:], "hno:l:b:c:")
    except getopt.GetoptError as err:
        print str(err)
        usage()

    outfile = None
    label = "idle:free:fps_ave:kbps_ave"
    bitrate = None
    cmd = ""
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
        host = args[0]
        rtspurl = "rtsp://{}:43794/profile1".format(host)

        parsers = []
        parsers.append(TopParserV31())
        parsers.append(RtspParser())
        parsers.append(OverflowParser())

        tester = BitrateTester(rtspurl)
        keys = []
        for res in tester.run_test(parsers):
            if not keys:
                keys = res.keys()
                print keys
                if outfile:
                    print >> outfile, keys
            res_str = reduce(lambda x, y: str(x)+'\t'+str(y)，keys)

            print res_str
            if outfile:
                print >> outfile, res_str

        if outfile:
            outfile.close()

        import os
        os.system("notify-send done " + host)

    elif mode == "parse":
        op = OverflowParser()
        sh = TelShell(args[0], "root")
        oplog = sh.cmd("cat /sys/devices/platform/ocp/18040000.rts_soc_camera/streaminfo")
        print op.parse({"overflow": oplog})

    elif mode == "plot":
        if len(args) == 0:
            print "missing a argment"
            usage()

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
        if not cmd:
            print "Need a cmd"
            exit(-1)
        sh = TelShell(args[0], "root")
        print sh.cmd(cmd)
