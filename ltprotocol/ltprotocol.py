"""Provides a Twisted-based client and server implementation for protocols which
begin with a length and type field.  Create your protocol by constructing an
LTProtocol with a list of LTMessage objects which specify your protocol.  Use
LTTwistedServer and LTTwistedClient to create a server or client.

@author David Underhill
@version 0.2.1 (2009-Sep-15)
"""

import logging
import struct

from twisted.internet.protocol  import Protocol, ReconnectingClientFactory, Factory
from twisted.internet           import reactor

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

    def __init__(self, msg_types, len_type='H', type_type='B'):
        """Creates an LTProtocol which recognizes a the specified list of LTMessage classes.

        @param msg_types  list of LTMessage classes which this protocol includes
        @param len_type   type of integer used for the length field (see struct doc for format chars)
        @param type_type  type of integer used for the type field (see struct doc for format chars)
        """
        # maps message type numbers to LTMessageType objects
        self.msg_types = {}
        for ltm in msg_types:
            self.msg_types[ltm.get_type()] = ltm
        self.len_type = len_type
        self.type_type = type_type

    def pack_with_header(self, lmt):
        """Creates a packed byte-string of this message given the body.
        @param lmt  packed byte-string representing the message body
        """
        body = lmt.pack()
        fmt = '> ' + self.len_type + self.type_type
        sz = struct.calcsize(fmt) + len(body)
        return struct.pack(fmt, sz, lmt.get_type()) + body

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
        """Creates a """
        self.factory = None  # set when used by a factory
        self.buf_accum = ''
        self.packet = ""
        self.plen = 0
        self.connected = False

    def connectionMade(self):
        # add function to transport so it is easy to send an LTProtocol message with it
        self.connected = True
        self.send = lambda ltm : self.transport.write(self.factory.lt_protocol.pack_with_header(ltm))
        self.factory.new_conn_callback(self)

    def connectionLost(self, reason):
        """Note that this protocol is no longer connected."""
        self.connected = False
        self.factory.lost_conn_callback(self)

    def dataReceived(self, data):
        """Called when data is received on a connection."""
        self.packet += data
        self.plen += len(data)
        len_fmt = "> " + self.factory.lt_protocol.len_type
        len_fmt_sz = struct.calcsize(len_fmt)
        type_fmt = "> " + self.factory.lt_protocol.type_type
        type_fmt_sz = struct.calcsize(type_fmt)
        tot_sz = len_fmt_sz + type_fmt_sz

        while self.plen >= len_fmt_sz:
            lenNeeded = struct.unpack(len_fmt, self.packet[0:len_fmt_sz])[0]

            # process the packet if we have received the whole thing
            if self.plen >= lenNeeded:
                buf = self.packet[0:lenNeeded]
                self.packet = self.packet[lenNeeded:]
                self.plen -= lenNeeded

                type_val = struct.unpack(type_fmt, buf[len_fmt_sz:tot_sz])[0]
                lt_msg = self.factory.lt_protocol.unpack_received_msg(type_val, buf[tot_sz:])
                self.factory.recv_callback(self, lt_msg)
            else:
                # not enough bytes for a full packet yet
                break

    def __str__(self):
        """Returns a string representation of the peer's information."""
        return str(self.transport.getPeer())

class LTTwistedServerProtocol(LTTwistedProtocol):
    def __init__(self, verbose=True):
        LTTwistedProtocol.__init__(self)
        self.verbose = verbose

    def connectionMade(self):
        """Called when a new connection is setup."""
        self.factory.numProtocols = self.factory.numProtocols + 1
        if self.verbose:
            fmt = "Client has connected to the LTProtocol server (%u update connections now live)"
            logging.info(fmt % self.factory.numProtocols)

        # give the parent a hook into into our TCP connection so it can send data
        self.factory.connections.append(self)

        # let the super-class setup the send() method and issue new_conn_callback
        LTTwistedProtocol.connectionMade(self)

    def connectionLost(self, reason):
        """Called when a connection is terminated."""
        self.factory.numProtocols = self.factory.numProtocols - 1
        if self.verbose:
            fmt = "LTProtocol server connection to client lost (%u update connections now live): %s"
            logging.info(fmt % (self.factory.numProtocols, reason.getErrorMessage()))
        self.factory.connections.remove(self)

        # let the super-class cleanup
        LTTwistedProtocol.connectionLost(self, reason)

class LTTwistedClient(ReconnectingClientFactory):
    """A twisted-based client for protocols which begin with length and type."""
    protocol = LTTwistedProtocol

    def __init__(self, lt_protocol, recv_callback,
                 new_conn_callback=None, lost_conn_callback=None,
                 verbose=True):
        """Creates an Twisted client factory for the specified lt_protocol.

        @param lt_protocol    the LTProtocol protocol class the server uses to communicate
        @param recv_callback  the function to call when a message is received; it must take
                              two arguments (an LTTwistedProtocol object and an LTMessage object)
        @param new_conn_callback  called with one argument (a LTProtocol) when a new connection is made
        @param lost_conn_callback  called with one argument (a LTProtocol) when a connection is lost
        @param verbose        whether to print messages about connection status changing

        @return  the client factory (has a field connections with a list of active connections)
        """
        self.lt_protocol = lt_protocol
        self.recv_callback = recv_callback
        self.new_conn_callback = new_conn_callback if new_conn_callback else lambda p : None
        self.lost_conn_callback = lost_conn_callback if lost_conn_callback else lambda p : None
        self.ip = None
        self.port = None
        self.packet = ""
        self.plen = 0
        self.verbose = verbose

    def connect(self, ip, port):
        self.ip = ip
        self.port = port
        reactor.connectTCP(ip, port, self)

    def startedConnecting(self, _):
        if self.verbose:
            logging.debug('Trying to connect to LT server at %s:%s' % (str(self.ip), str(self.port)))

    def buildProtocol(self, _):
        # reset the packet buffer whenever we renew the connection
        self.packet = ""
        self.plen = 0
        if self.verbose:
            logging.info('Connected to the server at %s:%s' % (str(self.ip), str(self.port)))

        # once we successfully connect, reset the retry wait time
        self.resetDelay()
        proto = self.protocol()
        proto.factory = self
        return proto

    def clientConnectionLost(self, connector, reason):
        if self.verbose:
            fmt = 'Connection to the server at %s:%s lost: %s'
            logging.info(fmt % (str(self.ip), str(self.port), reason.getErrorMessage()))
        ReconnectingClientFactory.clientConnectionLost(self, connector, reason)

    def clientConnectionFailed(self, connector, reason):
        if self.verbose:
            fmt = 'Connection to the server at %s:%s failed: %s'
            logging.info(fmt % (str(self.ip), str(self.port), reason.getErrorMessage()))
        ReconnectingClientFactory.clientConnectionFailed(self, connector, reason)

class LTTwistedServer(Factory):
    """A twisted-based server for protocols which begin with length and type."""
    protocol = LTTwistedServerProtocol

    def __init__(self, lt_protocol, recv_callback,
                 new_conn_callback=None, lost_conn_callback=None,
                 verbose=True):
        """Creates an Twisted server factory for the specified lt_protocol.

        @param lt_protocol    the LTProtocol protocol class the server uses to communicate
        @param recv_callback  the function to call when a message is received; it must take
                              two arguments (an LTTwistedProtocol object and an LTMessage object)
        @param new_conn_callback  called with one argument (a connection) when a new connection is made
        @param lost_conn_callback  called with one argument (a LTProtocol) when a connection is lost
        @param verbose        whether to print messages when they are sent

        @return  the server factory (has a field connections with a list of active connections)
        """
        self.lt_protocol = lt_protocol
        self.recv_callback = recv_callback
        self.new_conn_callback = new_conn_callback if new_conn_callback else lambda p : None
        self.lost_conn_callback = lost_conn_callback if lost_conn_callback else lambda p : None
        self.connections = []
        self.numProtocols = 0
        self.verbose = verbose

    def listen(self, port):
        """Starts this Twisted server listening on the specified port.

        @param port           the port the server listens on
        """
        reactor.listenTCP(port, self)

    def send(self, ltm):
        """Sends a LTMessage to all connected clients."""
        buf = self.lt_protocol.pack_with_header(ltm)
        for conn in self.connections:
            conn.transport.write(buf)
            if self.verbose:
                logging.debug('  sent %s' % str(ltm))

    def send_msg_to_client(self, conn, ltm):
        """Sends a LTMessage to the specified client connection."""
        buf = self.lt_protocol.pack_with_header(ltm)
        conn.transport.write(buf)
