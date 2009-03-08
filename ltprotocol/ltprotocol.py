"""Provides a Twisted-based client and server implementation for protocols which
begin with a length and type field.  Create your protocol by constructing an
LTProtocol with a list of LTMessage objects which specify your protocol.  Use
LTTwistedServer and LTTwistedClient to create a server or client.

@author David Underhill
@version 0.1 (2009-Mar-08)
"""

from twisted.internet.protocol  import Protocol, ReconnectingClientFactory, Factory
from twisted.internet           import reactor
import struct

class LTMessage:
    """This class should be overridden to define specific messages which begin
       with length and type.
    """
    @staticmethod
    def get_type():
        """Returns the type identifying this message (a unique integer)."""
        return None

    def __init__(self):
        pass

    def pack_with_header(self):
        """Creates a packed byte-string of this message given the body.
        @param body  packed byte-string representing the message body
        """
        body = self.pack()
        return struct.pack('> 2I', len(body) + 8, self.get_type()) + body

    def pack(self):
        """Creates a packed byte-string of this message."""
        # Must be overridden by subclasses to return the packed message.
        pass

    @staticmethod
    def unpack(body):
        """Unpacks the body of a message."""
        # Must be overridden by subclasses to return the unpacked message.
        pass

class LTProtocol():
    """Defines a protocol whose messages are in the form length, type, and body."""

    def __init__(self, msg_types):
        """Creates an LTProtocol which recognizes a the specified list of LTMessage classes.

        @param msg_types  list of LTMessage classes which this protocol includes
        """
        # maps message type numbers to LTMessageType objects
        self.msg_types = {}
        for ltm in msg_types:
            self.msg_types[ltm.get_type()] = ltm

    def unpack_received_msg(self, type_val, body):
        """Returns the next fully-received message from sock, or None if the type is unknown."""
        if self.msg_types.has_key(type_val):
            return self.msg_types[type_val].unpack(body)
        else:
            return None # unknown message type

class LTTwistedProtocol(Protocol):
    """A Twisted protocol whose messages begin with length and type."""
    # live connections a server for this protocol is serving
    def __init__(self):
        self.factory = None  # set when used by a factory
        self.buf_accum = ''
        self.packet = ""
        self.plen = 0

    def dataReceived(self, data):
        """Called when data is received on a connection."""
        self.packet += data
        self.plen += len(data)

        while self.plen >= 4:
            lenNeeded = struct.unpack("> I", self.packet[0:4])[0]

            # process the packet if we have received the whole thing
            if self.plen >= lenNeeded:
                buf = self.packet[0:lenNeeded]
                self.packet = self.packet[lenNeeded:]
                self.plen -= lenNeeded

                print 'unpacking packet of length %u' % lenNeeded
                type_val = struct.unpack("> I", buf[4:8])[0]
                lt_msg = self.factory.lt_protocol.unpack_received_msg(type_val, buf[8:])
                self.factory.recv_callback(lt_msg)
            else:
                # not enough bytes for a full packet yet
                break

class LTTwistedServerProtocol(LTTwistedProtocol):
    def __init__(self):
        LTTwistedProtocol.__init__(self)

    def connectionMade(self):
        """Called when a new connection is setup."""
        self.factory.numProtocols = self.factory.numProtocols + 1
        fmt = "Client has connected to the LTProtocol server (%u update connections now live)"
        print fmt % self.factory.numProtocols

        # give the parent a hook into into our TCP connection so it can send data
        self.factory.connections.append(self)

    def connectionLost(self, reason):
        """Called when a connection is terminated."""
        self.factory.numProtocols = self.factory.numProtocols - 1
        fmt = "LTProtocl server connection to client lost (%u update connections now live): %s"
        print fmt % (self.factory.numProtocols, reason.getErrorMessage())
        self.factory.connections.remove(self)

class LTTwistedClient(ReconnectingClientFactory):
    """A twisted-based client for protocols which begin with length and type."""
    protocol = LTTwistedProtocol

    def __init__(self, lt_protocol, recv_callback):
        """Creates an Twisted client factory for the specified lt_protocol.

        @param lt_protocol    the LTProtocol protocol class the server uses to communicate
        @param recv_callback  the function to call when a message is received; it must take
                              one argument (an LTMessage object)

        @return  the client factory (has a field connections with a list of active connections)
        """
        self.lt_protocol = lt_protocol
        self.recv_callback = recv_callback
        self.ip = None
        self.port = None
        self.packet = ""
        self.plen = 0

    def connect(self, ip, port):
        self.ip = ip
        self.port = port
        reactor.connectTCP(ip, port, self)

    def startedConnecting(self, _):
        print 'Trying to connect to LT server at %s:%s' % (str(self.ip), str(self.port))

    def buildProtocol(self, _):
        # reset the packet buffer whenever we renew the connection
        self.packet = ""
        self.plen = 0
        print 'Connected to the server at %s:%s' % (str(self.ip), str(self.port))

        # once we successfully connect, reset the retry wait time
        self.resetDelay()
        proto = LTTwistedProtocol()
        proto.factory = self
        return proto

    def clientConnectionLost(self, connector, reason):
        fmt = 'Connection to the Laptop at %s:%s lost: %s'
        print fmt % (str(self.ip), str(self.port), reason.getErrorMessage())
        ReconnectingClientFactory.clientConnectionLost(self, connector, reason)

    def clientConnectionFailed(self, connector, reason):
        fmt = 'Connection to the Laptop at %s:%s failed: %s'
        print fmt % (str(self.ip), str(self.port), reason.getErrorMessage())
        ReconnectingClientFactory.clientConnectionFailed(self, connector, reason)

class LTTwistedServer(Factory):
    """A twisted-based server for protocols which begin with length and type."""
    protocol = LTTwistedServerProtocol

    def __init__(self, lt_protocol, recv_callback):
        """Creates an Twisted server factory for the specified lt_protocol.

        @param lt_protocol    the LTProtocol protocol class the server uses to communicate
        @param recv_callback  the function to call when a message is received; it must take
                              one argument (an LTMessage object)

        @return  the server factory (has a field connections with a list of active connections)
        """
        self.lt_protocol = lt_protocol
        self.recv_callback = recv_callback
        self.connections = []
        self.numProtocols = 0

    def listen(self, port):
        """Starts this Twisted server listening on the specified port.

        @param port           the port the server listens on
        """
        reactor.listenTCP(port, self)

    def send(self, ltm):
        """Sends a LTMessage to all connected clients."""
        buf = ltm.pack_with_header()
        for conn in self.connections:
            conn.transport.write(buf)
            print '  sent %s' % str(ltm)

    def send_msg_to_client(self, conn, ltm):
        """Sends a LTMessage to the specified client connection."""
        buf = ltm.pack_with_header()
        conn.transport.write(buf)
