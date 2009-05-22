#!/usr/bin/env python
# To try out this test, run both of the following:
#     python test_ltprotocol.py server
#     python test_ltprotocol.py client

from ltprotocol.ltprotocol import LTMessage, LTProtocol, LTTwistedClient, LTTwistedServer
from twisted.internet import reactor
import struct, sys

class NumMsg(LTMessage):
    @staticmethod
    def get_type():
        return 1

    def __init__(self, n):
        LTMessage.__init__(self)
        self.num = n

    def pack(self):
        return struct.pack("> I", self.num)

    @staticmethod
    def unpack(body):
        return NumMsg(struct.unpack("> I", body)[0])

    def __str__(self):
        return str(self.num)

class StrMsg(LTMessage):
    @staticmethod
    def get_type():
        return 2

    def __init__(self, s):
        LTMessage.__init__(self)
        self.str = s

    def pack(self):
        return struct.pack("> %us" % len(self.str), self.str)

    @staticmethod
    def unpack(body):
        return StrMsg(struct.unpack("> %us" % len(body), body)[0])

    def __str__(self):
        return self.str

TEST_PROTOCOL = LTProtocol([NumMsg, StrMsg], 'H', 'B')
def print_ltm(prefix, proto, ltm):
    print '%s got: %s' % (prefix, str(ltm))

def print_disconnect(proto):
    print 'disconnected!'

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print >> sys.stderr, "usage: ./test_ltprotocol.py TYPE"
        sys.exit(-1)

    what = sys.argv[1]
    if what != "client" and what != "server":
        print >> sys.stderr, "TYPE must be client or server"
        sys.exit(-1)

    # periodically sends some messages
    def periodic_send(proto):
        if proto.connected:
            print 'sending ...'
            proto.send(NumMsg(200))
            proto.send(StrMsg("hello world!"))
            proto.send(NumMsg(7))
            reactor.callLater(1, lambda : periodic_send(proto))

    if what == "client":
        client = LTTwistedClient(TEST_PROTOCOL,
                                 lambda p, m : print_ltm('client', p, m))
        client.connect('127.0.0.1', 9999)
    else:
        server = LTTwistedServer(TEST_PROTOCOL,
                                 lambda p, m : print_ltm('server', p, m),
                                 periodic_send,
                                 print_disconnect)
        server.listen(9999)

    reactor.run()
