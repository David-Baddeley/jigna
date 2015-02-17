#
# Enthought product code
#
# (C) Copyright 2013 Enthought, Inc., Austin, TX
# All right reserved.
#

from __future__ import absolute_import

# Standard Library
import os
from os.path import join

# Local Library
from .qt import QtGui


class HTMLWidget(QtGui.QWidget):
    """ A Qt based HTML widget to render the jigna template with a given
    domain model context. """

    def __init__(
        self, parent=None, window_flags=0, template=None, context=None
    ):
        super(HTMLWidget, self).__init__(parent, window_flags)

        self.template = template
        self.context = context

        self._create()

    def execute_js(self, js):
        """ Execute the given js string on the HTML widget.
        """
        return self._widget.execute_js(js)

    #### Private protocol #####################################################

    def _create(self):
        """ Create the jigna widget to render the template with the context.
        """

        # Set up the QtServer to serve the domain models in context
        from jigna.qt_server import QtServer
        self._server = QtServer(
            base_url = join(os.getcwd(), self.template.base_url),
            html     = self.template.html,
            context  = self.context
        )
        self._server.initialize()

        # Set up the client
        self._widget = self._server.widget
        self._widget.create(parent=self)
        size = self.template.recommended_size
        self._widget.control.resize(size[0], size[1])

        # Connect the client to the server
        self._server.connect(self._widget)