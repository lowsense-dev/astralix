try:
    from isal import igzip as gzip
except ImportError:
    import gzip
import struct
import io

from ..._security import MAX_UNCOMPRESSED_SIZE

from .. import TLObject


class GzipPacked(TLObject):
    CONSTRUCTOR_ID = 0x3072CFA1

    def __init__(self, data):
        self.data = data

    @staticmethod
    def gzip_if_smaller(content_related, data):
        """Calls bytes(request), and based on a certain threshold,
        optionally gzips the resulting data. If the gzipped data is
        smaller than the original byte array, this is returned instead.

        Note that this only applies to content related requests.
        """
        if content_related and len(data) > 512:
            gzipped = bytes(GzipPacked(data))
            return gzipped if len(gzipped) < len(data) else data
        else:
            return data

    def __bytes__(self):
        return struct.pack("<I", GzipPacked.CONSTRUCTOR_ID) + TLObject.serialize_bytes(
            gzip.compress(self.data)
        )

    @staticmethod
    def _decompress(data):
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
            result = stream.read(MAX_UNCOMPRESSED_SIZE + 1)
        if len(result) > MAX_UNCOMPRESSED_SIZE:
            raise ValueError("Decompressed MTProto payload exceeds size limit")
        return result

    @staticmethod
    def read(reader):
        constructor = reader.read_int(signed=False)
        if constructor != GzipPacked.CONSTRUCTOR_ID:
            raise ValueError("Invalid gzip constructor")
        return GzipPacked._decompress(reader.tgread_bytes())

    @classmethod
    def from_reader(cls, reader):
        return GzipPacked(GzipPacked._decompress(reader.tgread_bytes()))

    def to_dict(self):
        return {"_": "GzipPacked", "data": self.data}
