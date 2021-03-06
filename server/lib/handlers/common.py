from ..tm_utils import TransferHandler, Models
from ...constants import TransferStatus
import os


class UrlTransferHandler(TransferHandler):
    def __init__(self, url, transferId, itemId, psPath, user):
        TransferHandler.__init__(self, transferId, itemId, psPath, user)
        self.url = url
        self.flen = self._getFileFromItem()['size']

    def mkdirs(self):
        try:
            os.makedirs(os.path.dirname(self.psPath))
        except OSError:
            pass


class FileLikeUrlTransferHandler(UrlTransferHandler):
    BUFSZ = 32768

    def __init__(self, url, transferId, itemId, psPath, user):
        UrlTransferHandler.__init__(self, url, transferId, itemId, psPath, user)

    def transfer(self):
        Models.transferModel.setStatus(self.transferId, TransferStatus.TRANSFERRING,
                                       size=self.flen, transferred=0, setTransferStartTime=True)

        self.mkdirs()
        with open(self.psPath, 'wb') as outf, self.openInputStream() as inf:
            self.transferBytes(outf, inf)

    def openInputStream(self):
        raise NotImplementedError()

    def transferBytes(self, outf, inf):
        crt = 0
        while True:
            buf = inf.read(FileLikeUrlTransferHandler.BUFSZ)
            if not buf:
                break
            outf.write(buf)
            crt = crt + len(buf)
            self.updateTransferProgress(self.flen, crt)
