from __future__ import annotations

import argparse
import asyncio


async def relay(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    while data := await reader.read(4096):
        writer.write(data)
        await writer.drain()
    writer.close()
    await writer.wait_closed()


async def handle_client(
    client_reader: asyncio.StreamReader,
    client_writer: asyncio.StreamWriter,
    upstream_host: str,
    upstream_port: int,
) -> None:
    upstream_reader, upstream_writer = await asyncio.open_connection(
        upstream_host,
        upstream_port,
    )
    await asyncio.gather(
        relay(client_reader, upstream_writer),
        relay(upstream_reader, client_writer),
    )


async def serve(listen_port: int, upstream_host: str, upstream_port: int) -> None:
    server = await asyncio.start_server(
        lambda reader, writer: handle_client(
            reader,
            writer,
            upstream_host,
            upstream_port,
        ),
        host="127.0.0.1",
        port=listen_port,
    )
    async with server:
        await server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--listen-port", type=int, required=True)
    parser.add_argument("--upstream-host", default="127.0.0.1")
    parser.add_argument("--upstream-port", type=int, required=True)
    arguments = parser.parse_args()
    asyncio.run(
        serve(arguments.listen_port, arguments.upstream_host, arguments.upstream_port)
    )


if __name__ == "__main__":
    main()
