"""
OCR 接口冒烟测试脚本
"""
import base64
import json
import sys

import urllib.request


BASE = "http://127.0.0.1:8002"


def post_json(path, payload, allow_error=False):
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        if allow_error:
            return exc.code, exc.read().decode("utf-8")
        raise


def post_multipart(path, file_path, fields=None):
    boundary = "----test"
    parts = []
    if fields:
        for k, v in fields.items():
            parts.append(f"--{boundary}\r\n")
            parts.append(f'Content-Disposition: form-data; name="{k}"\r\n\r\n')
            parts.append(f"{v}\r\n")
    with open(file_path, "rb") as f:
        file_bytes = f.read()
    parts.append(f"--{boundary}\r\n")
    parts.append(
        f'Content-Disposition: form-data; name="file"; filename="test.png"\r\n'
        f"Content-Type: image/png\r\n\r\n"
    )
    parts.append(file_bytes.decode("latin1") + "\r\n")
    parts.append(f"--{boundary}--\r\n")
    body = "".join(parts).encode("latin1")
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.status, resp.read().decode("utf-8")


def write_test_png(path):
    """生成最小有效 PNG"""
    import struct
    import zlib

    width, height = 8, 8
    # 纯白 RGBA
    raw = b""
    for _ in range(height):
        raw += b"\x00" + b"\xff" * (width * 3)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    idat = zlib.compress(raw)

    def chunk(typ, data):
        return (
            struct.pack(">I", len(data))
            + typ
            + data
            + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
        )

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return path


def main():
    # 1) JSON 接口
    png_path = write_test_png("/tmp/test_ocr.png")
    with open(png_path, "rb") as f:
        png_bytes = f.read()
    b64 = base64.b64encode(png_bytes).decode()
    print("=== POST /api/ocr/ingredient (JSON) ===")
    status, body = post_json("/api/ocr/ingredient", {
        "imageBase64": b64,
        "returnMatches": True,
        "skinTags": ["sensitive"],
    })
    print("status:", status)
    print(json.dumps(json.loads(body), ensure_ascii=False, indent=2))

    # 2) Multipart 接口
    print("\n=== POST /api/ocr/ingredient/file (multipart) ===")
    status, body = post_multipart(
        "/api/ocr/ingredient/file",
        "/tmp/test_ocr.png",
        fields={"skin_tags": "sensitive,dry"},
    )
    print("status:", status)
    print(json.dumps(json.loads(body), ensure_ascii=False, indent=2))

    # 3) 错误用例：非图片（进入路由层校验后返回 415）
    print("\n=== POST /api/ocr/ingredient (not image) ===")
    status, body = post_json(
        "/api/ocr/ingredient",
        {
            "imageBase64": base64.b64encode(b"not-an-image").decode(),
            "returnMatches": True,
        },
        allow_error=True,
    )
    print("status:", status)
    print(body)


if __name__ == "__main__":
    main()
