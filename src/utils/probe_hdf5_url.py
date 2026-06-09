#!/usr/bin/env python3
"""Probe HDF5 structure over HTTP using byte-range reads (no full download).

Useful for ABC Atlas and other remote HDF5 archives where you want to know
what datasets exist (names, shapes, dtypes, chunking, compression, attrs)
before deciding whether to download the file. HDF5 metadata is small and
distributed near the start of the file, so a structure probe typically
costs just a few KB of HTTP regardless of file size.

Implements a minimal file-like object backed by requests' Range header so
h5py can do random-access seek/read without ever holding the full bytes
in memory.

Example:
    python src/utils/probe_hdf5_url.py \\
        https://ansrs-neuroglancer-poc.s3.us-west-2.amazonaws.com/HPF+flatmap/P56_HPF.hdf5
"""

import argparse
import io
import sys

import h5py
import numpy as np
import requests


class HttpRangeReader(io.RawIOBase):
    """File-like object that reads from a URL via HTTP Range requests."""

    def __init__(self, url, session=None):
        self.url = url
        self.session = session or requests.Session()
        head = self.session.head(url, allow_redirects=True)
        head.raise_for_status()
        if "Content-Length" not in head.headers:
            raise RuntimeError(
                f"Server did not return Content-Length for {url}; "
                "byte-range probing requires a known total size."
            )
        self.size = int(head.headers["Content-Length"])
        self.pos = 0
        self.n_requests = 0
        self.n_bytes = 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def seek(self, pos, whence=0):
        if whence == 0:
            self.pos = pos
        elif whence == 1:
            self.pos += pos
        elif whence == 2:
            self.pos = self.size + pos
        return self.pos

    def tell(self):
        return self.pos

    def read(self, size=-1):
        if size is None or size < 0 or size > self.size - self.pos:
            size = self.size - self.pos
        if size == 0:
            return b""
        end = self.pos + size - 1
        r = self.session.get(
            self.url, headers={"Range": f"bytes={self.pos}-{end}"}
        )
        r.raise_for_status()
        data = r.content
        self.pos += len(data)
        self.n_requests += 1
        self.n_bytes += len(data)
        return data

    def readinto(self, b):
        data = self.read(len(b))
        n = len(data)
        b[:n] = data
        return n


def probe(url: str) -> None:
    print(f"Probing {url}", flush=True)
    reader = HttpRangeReader(url)
    print(
        f"  total size: {reader.size:,} bytes "
        f"({reader.size / 1024**3:.2f} GiB)"
    )

    with h5py.File(reader, mode="r") as h5:
        if h5.attrs:
            print()
            print("Root attrs:")
            for k, v in h5.attrs.items():
                print(f"  {k!r} = {v!r}")
        print()
        print("=== HDF5 tree ===")

        def walker(name, obj):
            if isinstance(obj, h5py.Dataset):
                attrs = dict(obj.attrs)
                print(
                    f"  DS {name:<48} shape={obj.shape}  dtype={obj.dtype}  "
                    f"chunks={obj.chunks}  comp={obj.compression}"
                )
                for k, v in attrs.items():
                    v_disp = v if not isinstance(v, (bytes, np.bytes_)) else v[:80]
                    print(f"      @{k!r} = {v_disp!r}")
            elif isinstance(obj, h5py.Group):
                attrs = dict(obj.attrs)
                print(f"  GRP {name:<48} attrs={attrs}")

        h5.visititems(walker)

    print()
    print(
        f"HTTP cost: {reader.n_requests} range requests, "
        f"{reader.n_bytes / 1024:.1f} KB total"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "url",
        help="HTTP(S) URL of the remote HDF5 file. The server must "
             "support HEAD and HTTP Range requests (S3, most CDNs do).",
    )
    args = parser.parse_args()
    probe(args.url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
