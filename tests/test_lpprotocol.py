#!/usr/bin/env python
# To try out this test, run both of the following:
#     python test_lpprotocol.py server
#     python test_lpprotocol.py client

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

def print_ltm(prefix, ltm):
    print '%s got: %s' % (prefix, str(ltm))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print >> sys.stderr, "usage: ./test_ltprotocol.py TYPE"
        sys.exit(-1)

    what = sys.argv[1]
    if what != "client" and what != "server":
        print >> sys.stderr, "TYPE must be client or server"
        sys.exit(-1)

    p = LTProtocol([NumMsg, StrMsg], 'H', 'B')
    if what == "client":
        client = LTTwistedClient(p, lambda m : print_ltm('client', m))
        client.connect('127.0.0.1', 9999)
    else:
        server = LTTwistedServer(p, lambda m : print_ltm('server', m))
        server.listen(9999)

        # check for new connections every 1 sec and send some data to the client
        # before closing the connection
        def callback():
            if len(server.connections) > 0:
                print 'sending ...'
                server.send(NumMsg(200))
                server.send(StrMsg("hello world!"))
                server.send(NumMsg(7))
                for c in server.connections:
                    c.transport.loseConnection()
            reactor.callLater(1, callback)
        reactor.callLater(1, callback)

    reactor.run()
