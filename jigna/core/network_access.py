#
# Jigna product code
#
# (C) Copyright 2013 Enthought, Inc., Austin, TX
# All right reserved.
#
# This file is confidential and NOT open source.  Do not distribute.
#

# Standard library imports.
import logging
import sys
import threading
from StringIO import StringIO

# System library imports.
from pyface.qt import QtCore
from pyface.qt.QtNetwork import QNetworkAccessManager, QNetworkReply, \
    QNetworkRequest

# Logger.
logger = logging.getLogger(__name__)


class ProxyAccessManager(QNetworkAccessManager):
    """ A QNetworkAccessManager subclass which proxies requests for a set of
    hosts and schemes.
    """
    def __init__(self, access_manager=None, hosts={}):
        super(ProxyAccessManager, self).__init__()
        self.access_manager = access_manager
        self.hosts = hosts

    def get_url_handler(self, url):
        """ Returns the WSGI callable to be used for specified url. 
        """
        str_url = url.toString()

        if self.access_manager is not None:
            access_handler = self.access_manager.get_access_handler(str_url)
            if access_handler is not None:
                return access_handler.app

        return self.hosts.get(url.host())

    def inject(self, webview):
        """ Replace the old QNetworkAccessManager instance with this instance.
        """
        old_manager = webview.page().networkAccessManager()

        self.setCache(old_manager.cache())
        self.setCookieJar(old_manager.cookieJar())
        self.setProxy(old_manager.proxy())
        self.setProxyFactory(old_manager.proxyFactory())
        webview.page().setNetworkAccessManager(self)

    ###########################################################################
    # QNetworkAccessManager interface
    ###########################################################################

    def createRequest(self, operation, request, data):
        """ Create a ProxyReply request if url handler is provided by
        `access_manager`, else defer to the original QNetworkAccessManager
        `createRequest` method.
        """
        url = request.url()
        str_url = url.toString()
        handler = self.get_url_handler(url)
        if handler is not None:
            logger.debug('Proxying request to %s' % str_url)
            data_str = data and data.readAll() or ''
            return ProxyReply(self, url, operation, request, data_str, handler)
        
        # Default case, let superclass handle normal web access
        return super(ProxyAccessManager, self).createRequest(
            operation, request, data)


class ProxyReply(QNetworkReply):
    """ QNetworkReply subclass to send a specific request to local wsgi app.
    """
    def __init__(self, parent, url, operation, req, data, handler):
        """ handler is the wsgi app """
        super(ProxyReply, self).__init__(parent)
        self.setRequest(req)
        self.setOperation(operation)
        self.setUrl(url)

        self.req_data = data
        self.handler = handler

        self.buffer = ''
        self._buflock = threading.Lock()
        self.aborted = False

        self.open(self.ReadOnly)

        self._worker = ProxyReplyWorker(self)
        self._worker.start()

        # Handle synchronous requests (webkit sync ajax requests)
        # req.Attribute.QSynchronousHttpNetworkReply may not be defined for
        # pyside compiled with qt 4.7 but still works with qt 4.8
        # QSynchronousHttpNetworkReply = DownloadBufferAttribute + 1 = 16
        if req.attribute(req.Attribute(16)):
            self._worker.wait()

    ###########################################################################
    # QNetworkReply interface
    ###########################################################################

    def abort(self):
        if not self.aborted:
            self.aborted = True
            self.setError(self.OperationCanceledError,
                          'Request Aborted')

    def bytesAvailable(self):
        return super(ProxyReply, self).bytesAvailable() + len(self.buffer)

    def isSequential(self):
        return True

    def readData(self, maxSize):
        with self._buflock:
            data, self.buffer = self.buffer[:maxSize], self.buffer[maxSize:]
        return data


class ProxyReplyWorker(QtCore.QThread):
    """ Worker thread to fetch urls for QNetworkProxy. """

    # Signals to forward to ProxyReply
    metaDataChanged = QtCore.Signal()
    readyRead = QtCore.Signal()
    finished = QtCore.Signal()

    OPERATIONS = {QNetworkAccessManager.GetOperation: 'GET',
                  QNetworkAccessManager.PostOperation: 'POST',}

    def __init__(self, reply, parent=None):
        super(ProxyReplyWorker, self).__init__(parent)
        self.reply = reply
        self.metaDataChanged.connect(self.reply.metaDataChanged)
        self.readyRead.connect(self.reply.readyRead)
        self.finished.connect(self.reply.finished)

    ###########################################################################
    # QThread interface.
    ###########################################################################

    def run(self):
        """ handles the request by acting as a WSGI forwarding server. """
        reply = self.reply
        url = reply.url()
        req = reply.request()

        # WSGI environ variables
        env = {
            'REQUEST_METHOD': self.OPERATIONS[reply.operation()],
            'SCRIPT_NAME': '',
            'PATH_INFO': url.path(),
            'SERVER_NAME': url.host(),
            'SERVER_PORT': '80',
            'SERVER_PROTOCOL': 'HTTP/1.1',
            'QUERY_STRING': str(url.encodedQuery()),
            'wsgi.version': (1, 0),
            'wsgi.url_scheme': url.scheme(),
            'wsgi.input': StringIO(reply.req_data),
            'wsgi.errors': sys.stderr,
            'wsgi.multithread': False,
            'wsgi.multiprocess': True,
            'wsgi.run_once': False,
        }

        # Set WSGI HTTP request headers
        for head_name in req.rawHeaderList():
            env_name = 'HTTP_' + head_name.data().replace('-','_').upper()
            head_val = req.rawHeader(head_name)
            env[env_name] = head_val.data()

        try:
            local_buf = []
            local_buf_len = 0
            for read in reply.handler(env, self._start_response):
                if reply.aborted:
                    return
                local_buf.append(str(read))
                local_buf_len += len(read)
                if local_buf_len >= 8192:
                    # Do not write to buffer on every read, app is slowed down
                    # due to lock contention
                    with reply._buflock:
                        reply.buffer += ''.join(local_buf)
                    local_buf = []
                    local_buf_len = 0
                    self.readyRead.emit()
            with reply._buflock:
                reply.buffer += ''.join(local_buf)

        except Exception as e:
            if reply.aborted:
                return
            reply.setAttribute(QNetworkRequest.HttpStatusCodeAttribute, 500)
            reply.setAttribute(QNetworkRequest.HttpReasonPhraseAttribute,
                               'Internal Error')
            with reply._buflock:
                reply.buffer += 'WSGI Proxy "Server" Error.\n' + str(e)
        finally:
            self.readyRead.emit()
            self.finished.emit()

    ###########################################################################
    # Private interface.
    ###########################################################################

    def _start_response(self, status, response_headers):
        """ WSGI start_response callable. """
        code, reason = status.split(' ', 1)
        self.reply.setAttribute(QNetworkRequest.HttpStatusCodeAttribute,
                          int(code))
        self.reply.setAttribute(QNetworkRequest.HttpReasonPhraseAttribute,
                          reason)
        for name, value in response_headers:
            self.reply.setRawHeader(name, str(value))

        self.metaDataChanged.emit()