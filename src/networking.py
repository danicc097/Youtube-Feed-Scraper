# Copyright (C) 2021 Daniel Castro

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from PyQt5.QtCore import QByteArray, QObject, QUrl, pyqtSignal, pyqtSlot
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest


class Sender(QObject):
    """
    To be used as QNetworkReply and QNetworkRequest ``originatingObject``.
    """
    def __init__(self, sender_name, sender_object):
        super(Sender, self).__init__()
        self._sender_name = sender_name
        self._sender_object = sender_object

    @property
    def sender_name(self):
        return self._sender_name

    @sender_name.setter
    def sender_name(self, name: str):
        if self.sender_name == name:
            return
        self.sender_name = name

    @property
    def sender_object(self):
        return self._sender_object

    @sender_object.setter
    def sender_object(self, object: QObject):
        if self.sender_object == object:
            return
        self.sender_object = object


class CustomNetworkManager(QObject):
    """QNetworkAccessManager wrapper to handle async downloads. \n
    Usage:
    ------
    ``foo = CustomNetworkManager()`` \n
    ``foo.downloaded.connect(lambda: global_client_loader())`` \n
    original sender and data are passed 
    
    ``foo.start_download(QUrl(my_url), sender)`` 
    execution continues. The download is tied to ``sender``.
    
    in main thread:
    ``def global_client_loader(sender,byte_array):`` \n
        ``sender.sender_name == "some_name":``
            ``do_stuff(sender,byte_array)``
    """
    downloaded = pyqtSignal(QObject, QByteArray)

    def __init__(self):
        super().__init__()  # init QObject
        self._manager = QNetworkAccessManager(finished=self._downloadFinished)

    @pyqtSlot(QNetworkReply)
    def _downloadFinished(self, reply: QNetworkReply):
        """Handle signal 'finished'.  A network request has finished."""
        error = reply.error()
        sender = reply.request().originatingObject()

        if error == QNetworkReply.NoError:
            _downloadedData = reply.readAll()
            reply.deleteLater()  # schedule as per docs
            self.downloaded.emit(sender, _downloadedData)
        else:
            print("[INFO] Error: {}".format(reply.errorString()))

    def start_download(self, url: str, sender: Sender):
        """Use in main application to start a download from ``url`` for
        a given object ``sender``."""
        request = QNetworkRequest(QUrl(url))
        request.setOriginatingObject(sender)  # keep track of download issuer
        self._manager.get(request)