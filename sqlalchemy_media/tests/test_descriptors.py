
import unittest
import io
import cgi
from os.path import dirname, abspath, join, split

from sqlalchemy_media.helpers import copy_stream, md5sum
from sqlalchemy_media.tests.helpers import simple_http_server, encode_multipart_data
from sqlalchemy_media.descriptors import AttachableDescriptor, LocalFileSystemDescriptor, CgiFieldStorageDescriptor, \
    UrlDescriptor, StreamDescriptor
from sqlalchemy_media.exceptions import MaximumLengthIsReachedError


class AttachableDescriptorsTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.this_dir = abspath(dirname(__file__))
        cls.stuff_path = join(cls.this_dir, 'stuff')
        cls.cat_jpeg = join(cls.stuff_path, 'cat.jpg')

    def test_stream(self):
        # guess content types from extension
        descriptor = AttachableDescriptor(io.BytesIO(b'Simple text'), extension='.txt')
        self.assertIsInstance(descriptor, StreamDescriptor)
        self.assertEqual(descriptor.content_type, 'text/plain')
        descriptor.seek(2)
        self.assertEqual(descriptor.tell(), 2)

        # guess extension from original filename
        descriptor = AttachableDescriptor(io.BytesIO(b'Simple text'), original_filename='letter.pdf')
        self.assertEqual(descriptor.extension, '.pdf')

        # guess extension from content type
        descriptor = AttachableDescriptor(io.BytesIO(b'Simple text'), content_type='application/json')
        self.assertEqual(descriptor.extension, '.json')

    def test_non_seekable(self):

        class NonSeekableStream(io.BytesIO):

            def seekable(self, *args, **kwargs):
                return False

        inp = b'abcdefghijklmnopqrstuvwxyz'
        descriptor = AttachableDescriptor(NonSeekableStream(inp), header_buffer_size=10)

        out = b''
        out += descriptor.read(9)
        self.assertEqual(descriptor.tell(), 9)
        out += descriptor.read(11)
        self.assertEqual(descriptor.tell(), 20)
        out += descriptor.read(10)
        self.assertEqual(out, inp)

        # Max length error
        descriptor = AttachableDescriptor(NonSeekableStream(inp), header_buffer_size=24, max_length=20)
        self.assertRaises(MaximumLengthIsReachedError, descriptor.read, 1)

        descriptor = AttachableDescriptor(NonSeekableStream(inp), header_buffer_size=10, max_length=20)
        self.assertRaises(MaximumLengthIsReachedError, descriptor.read, 22)

    def test_localfs(self):

        descriptor = AttachableDescriptor(self.cat_jpeg, width=100, height=80)
        self.assertIsInstance(descriptor, LocalFileSystemDescriptor)

        # Must be determined from the given file's extension: .jpg
        self.assertEqual(descriptor.content_type, 'image/jpeg')
        self.assertEqual(descriptor.original_filename, self.cat_jpeg)

        # noinspection PyUnresolvedReferences
        self.assertEqual(descriptor.width, 100)
        # noinspection PyUnresolvedReferences
        self.assertEqual(descriptor.height, 80)

        buffer = io.BytesIO()
        copy_stream(descriptor, buffer)
        buffer.seek(0)
        self.assertEqual(md5sum(buffer), md5sum(self.cat_jpeg))

    def test_url(self):

        with simple_http_server(self.cat_jpeg) as http_server:
            url = 'http://%s:%s' % http_server.server_address
            descriptor = AttachableDescriptor(url)

            self.assertIsInstance(descriptor, UrlDescriptor)
            self.assertEqual(descriptor.content_type, 'image/jpeg')  # Must be determined from response headers
            self.assertEqual(descriptor.content_length, 70279)  # Must be determined from response headers
            self.assertEqual(descriptor.original_filename, url)

    def test_cgi_field_storage(self):
        # encode a multipart form
        content_type, body, content_length = encode_multipart_data(files=dict(cat=self.cat_jpeg))
        environ = {
            'REQUEST_METHOD': 'POST',
            'CONTENT_TYPE': content_type,
            'CONTENT_LENGTH': content_length
        }

        storage = cgi.FieldStorage(body, environ=environ)

        descriptor = AttachableDescriptor(storage['cat'])
        self.assertIsInstance(descriptor, CgiFieldStorageDescriptor)
        self.assertEqual(descriptor.content_type, 'image/jpeg')
        self.assertEqual(descriptor.original_filename, split(self.cat_jpeg)[1])

        buffer = io.BytesIO()
        copy_stream(descriptor, buffer)
        buffer.seek(0)
        self.assertEqual(md5sum(buffer), md5sum(self.cat_jpeg))


if __name__ == '__main__':  # pragma: no cover
    unittest.main()